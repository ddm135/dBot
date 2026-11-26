"""Login credentials per game, including the session the bot keeps."""

from collections.abc import Mapping
from typing import Any, NamedTuple

import asyncpg
from asyncpg_typed import RequiredJsonType, sql


class _Credential(NamedTuple):
    game: str
    fields: RequiredJsonType


_ALL_CREDENTIALS = sql(
    t"SELECT game, fields FROM game_credentials",
    resultset=_Credential,
)

_CREDENTIAL = sql(
    t"SELECT fields FROM game_credentials WHERE game = {1}",
    arg=str,
    resultset=tuple[RequiredJsonType],  # a union cannot be given as ``result=``
)

_SAVE_CREDENTIAL = sql(
    t"INSERT INTO game_credentials (game, fields) VALUES ({1}, {2}) "
    t"ON CONFLICT (game) DO UPDATE SET fields = EXCLUDED.fields",
    args=tuple[str, RequiredJsonType],
)

# Also used by the v0 import: existing credentials are kept.
INSERT_CREDENTIAL_IF_NEW = sql(
    t"INSERT INTO game_credentials (game, fields) VALUES ({1}, {2}) "
    t"ON CONFLICT (game) DO NOTHING",
    args=tuple[str, RequiredJsonType],
)

_DELETE_CREDENTIAL = sql(
    t"DELETE FROM game_credentials WHERE game = {1} RETURNING true",
    arg=str,
    result=bool,
)


class Credentials:
    """Login credentials per game, including the session the bot keeps."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def all(self) -> dict[str, dict[str, Any]]:
        async with self._pool.acquire() as conn:
            rows = await _ALL_CREDENTIALS.fetch(conn)
        return {row.game: row.fields for row in rows if isinstance(row.fields, dict)}

    async def get(self, game: str) -> dict[str, Any] | None:
        async with self._pool.acquire() as conn:
            row = await _CREDENTIAL.fetchrow(conn, game)
        return row[0] if row and isinstance(row[0], dict) else None

    async def save(self, game: str, fields: Mapping[str, Any]) -> None:
        async with self._pool.acquire() as conn:
            await _SAVE_CREDENTIAL.execute(conn, game, dict(fields))

    async def delete(self, game: str) -> bool:
        async with self._pool.acquire() as conn:
            return await _DELETE_CREDENTIAL.fetchrow(conn, game) is not None
