"""Small stores: live themes, game credentials, and search aliases."""

from collections.abc import Mapping
from typing import Any, Literal, NamedTuple

import asyncpg
from asyncpg_typed import RequiredJsonType, sql

type AliasKind = Literal["song", "deck"]

# -- live themes -------------------------------------------------------------------

_LIVE_THEME = sql(
    t"SELECT amount FROM live_themes WHERE user_id = {1} AND game = {2}",
    args=tuple[int, str],
    result=int,
)

_SET_LIVE_THEME = sql(
    t"INSERT INTO live_themes (user_id, game, amount) VALUES ({1}, {2}, {3}) "
    t"ON CONFLICT (user_id, game) DO UPDATE SET amount = EXCLUDED.amount",
    args=tuple[int, str, int],
)

# Also used by the v0 import: an existing amount is kept.
INSERT_LIVE_THEME_IF_NEW = sql(
    t"INSERT INTO live_themes (user_id, game, amount) VALUES ({1}, {2}, {3}) "
    t"ON CONFLICT (user_id, game) DO NOTHING",
    args=tuple[int, str, int],
)

# -- credentials -------------------------------------------------------------------


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

# -- search aliases ------------------------------------------------------------------


class _Alias(NamedTuple):
    kind: str
    code: int
    alias: str


_ALL_ALIASES = sql(
    t"SELECT kind, code, alias FROM search_aliases WHERE game = {1} ORDER BY alias",
    arg=str,
    resultset=_Alias,
)

_ADD_ALIAS = sql(
    t"INSERT INTO search_aliases (game, kind, code, alias) VALUES ({1}, {2}, {3}, {4}) "
    t"ON CONFLICT DO NOTHING RETURNING true",
    args=tuple[str, str, int, str],
    result=bool,
)

_REMOVE_ALIAS = sql(
    t"DELETE FROM search_aliases "
    t"WHERE game = {1} AND kind = {2} AND code = {3} AND alias = {4} RETURNING true",
    args=tuple[str, str, int, str],
    result=bool,
)


# -- display names ---------------------------------------------------------------------


class _DisplayName(NamedTuple):
    kind: str
    code: int
    name: str


_ALL_NAMES = sql(
    t"SELECT kind, code, name FROM display_names WHERE game = {1}",
    arg=str,
    resultset=_DisplayName,
)

_SET_NAME = sql(
    t"INSERT INTO display_names (game, kind, code, name) VALUES ({1}, {2}, {3}, {4}) "
    t"ON CONFLICT (game, kind, code) DO UPDATE SET name = EXCLUDED.name",
    args=tuple[str, str, int, str],
)

_CLEAR_NAME = sql(
    t"DELETE FROM display_names WHERE game = {1} AND kind = {2} AND code = {3} "
    t"RETURNING true",
    args=tuple[str, str, int],
    result=bool,
)


class DisplayNames:
    """Names shown instead of the game's own for chosen songs and decks."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def all(self, game: str) -> dict[tuple[AliasKind, int], str]:
        async with self._pool.acquire() as conn:
            rows = await _ALL_NAMES.fetch(conn, game)
        result: dict[tuple[AliasKind, int], str] = {}
        for row in rows:
            match row.kind:
                case "song" | "deck" as kind:
                    result[kind, row.code] = row.name
        return result

    async def set(self, game: str, kind: AliasKind, code: int, name: str) -> None:
        async with self._pool.acquire() as conn:
            await _SET_NAME.execute(conn, game, kind, code, name.strip())

    async def clear(self, game: str, kind: AliasKind, code: int) -> bool:
        async with self._pool.acquire() as conn:
            return await _CLEAR_NAME.fetchrow(conn, game, kind, code) is not None


class LiveThemes:
    """The most live-theme bonus a user has, per game."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get(self, user_id: int, game: str) -> int:
        async with self._pool.acquire() as conn:
            row = await _LIVE_THEME.fetchrow(conn, user_id, game)
        return row[0] if row else 0

    async def set(self, user_id: int, game: str, amount: int) -> None:
        async with self._pool.acquire() as conn:
            await _SET_LIVE_THEME.execute(conn, user_id, game, amount)


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


class Aliases:
    """Extra search terms for songs and decks (nicknames, romanisations)."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def all(self, game: str) -> dict[tuple[AliasKind, int], list[str]]:
        async with self._pool.acquire() as conn:
            rows = await _ALL_ALIASES.fetch(conn, game)
        result: dict[tuple[AliasKind, int], list[str]] = {}
        for row in rows:
            match row.kind:
                case "song" | "deck" as kind:
                    result.setdefault((kind, row.code), []).append(row.alias)
        return result

    async def add(self, game: str, kind: AliasKind, code: int, alias: str) -> bool:
        async with self._pool.acquire() as conn:
            added = await _ADD_ALIAS.fetchrow(
                conn, game, kind, code, alias.strip().casefold()
            )
        return added is not None

    async def remove(self, game: str, kind: AliasKind, code: int, alias: str) -> bool:
        async with self._pool.acquire() as conn:
            removed = await _REMOVE_ALIAS.fetchrow(
                conn, game, kind, code, alias.strip().casefold()
            )
        return removed is not None
