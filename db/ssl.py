"""When each SSL song and deck was last pinned."""

from datetime import date
from typing import NamedTuple

import asyncpg
from asyncpg_typed import sql


class LastAppearance(NamedTuple):
    # The names are the column names of ``_LAST``.
    song: date | None
    deck: date | None


_RECORD = sql(
    t"INSERT INTO ssl_history (game, day, song_code, deck_code) "
    t"VALUES ({1}, {2}, {3}, {4}) "
    t"ON CONFLICT (game, day) "
    t"DO UPDATE SET song_code = EXCLUDED.song_code, deck_code = EXCLUDED.deck_code",
    args=tuple[str, date, int, int],
)

_LAST = sql(
    t"SELECT max(day) FILTER (WHERE song_code = {2}) AS song, "
    t"       max(day) FILTER (WHERE deck_code = {3}) AS deck "
    t"FROM ssl_history "
    t"WHERE game = {1} AND ({4}::date IS NULL OR day < {4})",
    args=tuple[str, int, int, date | None],
    resultset=LastAppearance,
)

_PINNED_ON = sql(
    t"SELECT true FROM ssl_history WHERE game = {1} AND day = {2}",
    args=tuple[str, date],
    result=bool,
)

# Also used by the v0 import: an existing day is kept.
INSERT_MISSING = sql(
    t"INSERT INTO ssl_history (game, day, song_code, deck_code) "
    t"VALUES ({1}, {2}, {3}, {4}) ON CONFLICT DO NOTHING",
    args=tuple[str, date, int, int],
)


class SslHistory:
    """The days each SSL song and deck was pinned."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def record(
        self, game: str, day: date, song_code: int, deck_code: int
    ) -> None:
        """Record the song pinned on ``day`` (a later pin that day replaces it)."""
        async with self._pool.acquire() as conn:
            await _RECORD.execute(conn, game, day, song_code, deck_code)

    async def last(
        self, game: str, song_code: int, deck_code: int, *, before: date | None = None
    ) -> LastAppearance:
        """The latest day (optionally before ``before``) of a song and of its deck."""
        async with self._pool.acquire() as conn:
            row = await _LAST.fetchrow(conn, game, song_code, deck_code, before)
        assert row is not None  # an aggregate always returns a row
        return row

    async def pinned_on(self, game: str, day: date) -> bool:
        async with self._pool.acquire() as conn:
            return await _PINNED_ON.fetchrow(conn, game, day) is not None
