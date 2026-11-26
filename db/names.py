"""Display names and search aliases for songs and decks."""

from typing import Literal, NamedTuple

import asyncpg
from asyncpg_typed import sql

type AliasKind = Literal["song", "deck"]


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
