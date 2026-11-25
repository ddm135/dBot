"""Bonus ping subscriptions, delivery preferences, and the delivery log."""

from collections.abc import Collection
from datetime import date, timedelta
from typing import Literal, NamedTuple

import asyncpg
from asyncpg_typed import sql

type PingKind = Literal["start", "end"]

DEFAULT_OFFSET = 1  # hours before the day begins
LOG_KEEP_DAYS = 14


class PingPreferences(NamedTuple):
    # The names are the column names of ``_SET_PREFERENCES``.
    start_hours: int = DEFAULT_OFFSET
    end_hours: int = DEFAULT_OFFSET

    def hours(self, kind: PingKind) -> int:
        return self.start_hours if kind == "start" else self.end_hours


class _Subscriber(NamedTuple):
    user_id: int
    deck_code: int


class _UserPreferences(NamedTuple):
    user_id: int
    start_hours: int
    end_hours: int


# -- subscriptions -----------------------------------------------------------

# "RETURNING true" gives a row only if something was written, which is how
# a caller learns whether the subscription was new.
_SUBSCRIBE = sql(
    t"INSERT INTO bonus_subscriptions (user_id, game, deck_code) "
    t"VALUES ({1}, {2}, {3}) ON CONFLICT DO NOTHING RETURNING true",
    args=tuple[int, str, int],
    result=bool,
)

_ENSURE_PREFERENCES = sql(
    t"INSERT INTO bonus_preferences (user_id) VALUES ({1}) ON CONFLICT DO NOTHING",
    arg=int,
)

# Used by the v0 import.
IMPORT_SUBSCRIPTION = sql(
    t"INSERT INTO bonus_subscriptions (user_id, game, deck_code) VALUES ({1}, {2}, {3}) "
    t"ON CONFLICT DO NOTHING",
    args=tuple[int, str, int],
)

IMPORT_PREFERENCES = sql(
    t"INSERT INTO bonus_preferences (user_id, start_hours, end_hours) VALUES ({1}, {2}, {3}) "
    t"ON CONFLICT (user_id) DO NOTHING",
    args=tuple[int, int, int],
)

_UNSUBSCRIBE = sql(
    t"DELETE FROM bonus_subscriptions "
    t"WHERE user_id = {1} AND game = {2} AND deck_code = {3} RETURNING true",
    args=tuple[int, str, int],
    result=bool,
)

_DECKS_OF = sql(
    t"SELECT deck_code FROM bonus_subscriptions "
    t"WHERE user_id = {1} AND game = {2} ORDER BY deck_code",
    args=tuple[int, str],
    result=int,
)

_SUBSCRIBERS = sql(
    t"SELECT user_id, deck_code FROM bonus_subscriptions WHERE game = {1}",
    arg=str,
    resultset=_Subscriber,
)

# -- preferences ---------------------------------------------------------------

_PREFERENCES = sql(
    t"SELECT user_id, start_hours, end_hours FROM bonus_preferences "
    t"WHERE user_id = ANY({1}::bigint[])",
    arg=list[int],
    resultset=_UserPreferences,
)

# $2 and $3 are the hours to set, or NULL to leave one as it is; $4 is the
# default for a user who has no row yet.
_SET_PREFERENCES = sql(
    t"INSERT INTO bonus_preferences (user_id, start_hours, end_hours) "
    t"VALUES ({1}, COALESCE({2}::smallint, {4}::smallint), COALESCE({3}::smallint, {4}::smallint)) "
    t"ON CONFLICT (user_id) DO UPDATE SET "
    t"start_hours = COALESCE({2}::smallint, bonus_preferences.start_hours), "
    t"end_hours = COALESCE({3}::smallint, bonus_preferences.end_hours) "
    t"RETURNING start_hours, end_hours",
    args=tuple[int, int | None, int | None, int],
    resultset=PingPreferences,
)

# -- delivery log ----------------------------------------------------------------

_CLAIM = sql(
    t"INSERT INTO bonus_ping_log (user_id, game, day, kind) "
    t"VALUES ({1}, {2}, {3}, {4}) ON CONFLICT DO NOTHING RETURNING true",
    args=tuple[int, str, date, str],
    result=bool,
)

_RELEASE = sql(
    t"DELETE FROM bonus_ping_log "
    t"WHERE user_id = {1} AND game = {2} AND day = {3} AND kind = {4}",
    args=tuple[int, str, date, str],
)

_PRUNE = sql(
    t"WITH deleted AS (DELETE FROM bonus_ping_log WHERE day < {1} RETURNING 1) "
    t"SELECT count(*) FROM deleted",
    arg=date,
    result=int,
)


class BonusPings:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # -- subscriptions -------------------------------------------------------

    async def subscribe(self, user_id: int, game: str, deck_code: int) -> bool:
        async with self._pool.acquire() as conn, conn.transaction():
            added = await _SUBSCRIBE.fetchrow(conn, user_id, game, deck_code)
            await _ENSURE_PREFERENCES.execute(conn, user_id)
        return added is not None

    async def unsubscribe(self, user_id: int, game: str, deck_code: int) -> bool:
        async with self._pool.acquire() as conn:
            return (
                await _UNSUBSCRIBE.fetchrow(conn, user_id, game, deck_code) is not None
            )

    async def decks_of(self, user_id: int, game: str) -> list[int]:
        async with self._pool.acquire() as conn:
            return await _DECKS_OF.fetchcol(conn, user_id, game)

    async def subscribers(self, game: str) -> dict[int, set[int]]:
        """``{user_id: {deck_code}}`` for a game."""
        async with self._pool.acquire() as conn:
            rows = await _SUBSCRIBERS.fetch(conn, game)
        result: dict[int, set[int]] = {}
        for row in rows:
            result.setdefault(row.user_id, set()).add(row.deck_code)
        return result

    # -- preferences ---------------------------------------------------------

    async def preferences(
        self, user_ids: Collection[int]
    ) -> dict[int, PingPreferences]:
        if not user_ids:
            return {}
        async with self._pool.acquire() as conn:
            rows = await _PREFERENCES.fetch(conn, list(user_ids))
        found = {r.user_id: PingPreferences(r.start_hours, r.end_hours) for r in rows}
        return {u: found.get(u, PingPreferences()) for u in user_ids}

    async def set_preferences(
        self,
        user_id: int,
        *,
        start_hours: int | None = None,
        end_hours: int | None = None,
    ) -> PingPreferences:
        async with self._pool.acquire() as conn:
            row = await _SET_PREFERENCES.fetchrow(
                conn, user_id, start_hours, end_hours, DEFAULT_OFFSET
            )
        assert row is not None  # an upsert with RETURNING always returns a row
        return row

    # -- delivery log --------------------------------------------------------

    async def claim(self, user_id: int, game: str, day: date, kind: PingKind) -> bool:
        """Claim the right to send a ping; False if it was already sent."""
        async with self._pool.acquire() as conn:
            return await _CLAIM.fetchrow(conn, user_id, game, day, kind) is not None

    async def release(self, user_id: int, game: str, day: date, kind: PingKind) -> None:
        async with self._pool.acquire() as conn:
            await _RELEASE.execute(conn, user_id, game, day, kind)

    async def prune(self, today: date) -> int:
        async with self._pool.acquire() as conn:
            return await _PRUNE.fetchval(conn, today - timedelta(days=LOG_KEEP_DAYS))
