"""The most live-theme bonus a user has, per game."""

import asyncpg
from asyncpg_typed import sql

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
