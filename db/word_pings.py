"""Word pings: users who want a DM when a word is said in a server."""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Literal, NamedTuple

import asyncpg
from asyncpg_typed import sql

from templates import Raw, render

type IgnoreKind = Literal["user", "channel"]

# What may surround a pinged word: whitespace or punctuation (or the ends).
_BOUNDARY = r"""(?:[\s!@#$%^&*()\-_=+\[\]{}\\|;:'",<.>/?]+|^)"""
_BOUNDARY_END = r"""(?:[\s!@#$%^&*()\-_=+\[\]{}\\|;:'",<.>/?]+|$)"""

MAX_WORD_LENGTH = 100


class _PingRow(NamedTuple):
    guild_id: int
    user_id: int
    word: str
    pings: int


class _IgnoreRow(NamedTuple):
    guild_id: int
    user_id: int
    word: str
    kind: str
    target_id: int


_LOAD_PINGS = sql(
    t"SELECT guild_id, user_id, word, count AS pings FROM word_pings",
    resultset=_PingRow,
)

_LOAD_IGNORES = sql(
    t"SELECT guild_id, user_id, word, kind, target_id FROM word_ping_ignores",
    resultset=_IgnoreRow,
)

_ADD = sql(
    t"INSERT INTO word_pings (guild_id, user_id, word) VALUES ({1}, {2}, {3}) "
    t"ON CONFLICT DO NOTHING",
    args=tuple[int, int, str],
)

_REMOVE = sql(
    t"DELETE FROM word_pings WHERE guild_id = {1} AND user_id = {2} AND word = {3}",
    args=tuple[int, int, str],
)

_RECORD_PING = sql(
    t"UPDATE word_pings SET count = count + 1 "
    t"WHERE guild_id = {1} AND user_id = {2} AND word = {3}",
    args=tuple[int, int, str],
)

_IGNORE = sql(
    t"INSERT INTO word_ping_ignores (guild_id, user_id, word, kind, target_id) "
    t"VALUES ({1}, {2}, {3}, {4}, {5}) ON CONFLICT DO NOTHING",
    args=tuple[int, int, str, str, int],
)

_UNIGNORE = sql(
    t"DELETE FROM word_ping_ignores "
    t"WHERE guild_id = {1} AND user_id = {2} AND kind = {3} AND target_id = {4} "
    t"AND word = ANY({5}::text[])",
    args=tuple[int, int, str, int, list[str]],
)

# Also used by the v0 import: counts only go up, so the larger one is kept.
IMPORT_PING = sql(
    t"INSERT INTO word_pings (guild_id, user_id, word, count) VALUES ({1}, {2}, {3}, {4}) "
    t"ON CONFLICT (guild_id, user_id, word) "
    t"DO UPDATE SET count = GREATEST(word_pings.count, EXCLUDED.count)",
    args=tuple[int, int, str, int],
)
IMPORT_IGNORE = _IGNORE


def normalize(word: str) -> str:
    """Pings are case-insensitive, so words are stored lower-cased."""
    return " ".join(word.split()).casefold()


def word_pattern(word: str) -> re.Pattern[str]:
    """Only the word is escaped; the boundaries are regex on purpose."""
    pattern = render(t"{Raw(_BOUNDARY)}{word}{Raw(_BOUNDARY_END)}", re.escape)
    return re.compile(pattern, re.IGNORECASE)


@dataclass(slots=True)
class Subscription:
    """A user's ping for one word: how often it fired, and the users and channels they
    ignore.
    """

    count: int = 0
    users: set[int] = field(default_factory=set)  # ignored users
    channels: set[int] = field(default_factory=set)  # ignored channels

    def ignores(self, author_id: int, channel_id: int) -> bool:
        """Whether a message by ``author_id`` in ``channel_id`` is ignored."""
        return author_id in self.users or channel_id in self.channels


class WordPings:
    """All word pings, cached in memory and written through to Postgres.

    The bot reads them on every message, so the cache is the source of truth
    for reads. There is only ever one running instance (leader election).
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        # guild -> word -> user -> subscription
        self._data: dict[int, dict[str, dict[int, Subscription]]] = defaultdict(dict)
        self._patterns: dict[str, re.Pattern[str]] = {}

    async def load(self) -> None:
        """Read every ping from the database into memory."""
        data: dict[int, dict[str, dict[int, Subscription]]] = defaultdict(dict)
        async with self._pool.acquire() as conn:
            pings = await _LOAD_PINGS.fetch(conn)
            ignores = await _LOAD_IGNORES.fetch(conn)
        for row in pings:
            data[row.guild_id].setdefault(row.word, {})[row.user_id] = Subscription(
                count=row.pings
            )
        for ignore in ignores:
            sub = data[ignore.guild_id].get(ignore.word, {}).get(ignore.user_id)
            if sub is None:
                continue
            (sub.users if ignore.kind == "user" else sub.channels).add(ignore.target_id)
        self._data = data

    # -- reading -------------------------------------------------------------

    def get(self, guild_id: int, user_id: int, word: str) -> Subscription | None:
        return self._data.get(guild_id, {}).get(normalize(word), {}).get(user_id)

    def words_of(self, guild_id: int, user_id: int) -> dict[str, Subscription]:
        return {
            word: users[user_id]
            for word, users in self._data.get(guild_id, {}).items()
            if user_id in users
        }

    def matches(
        self, guild_id: int, content: str
    ) -> list[tuple[str, dict[int, Subscription]]]:
        """The words said in ``content`` and who is subscribed to each."""
        found = []
        for word, users in self._data.get(guild_id, {}).items():
            if not users:
                continue
            pattern = self._patterns.get(word)
            if pattern is None:
                pattern = self._patterns[word] = word_pattern(word)
            if pattern.search(content):
                found.append((word, users))
        return found

    # -- writing -------------------------------------------------------------

    async def add(self, guild_id: int, user_id: int, word: str) -> bool:
        word = normalize(word)
        if not word or len(word) > MAX_WORD_LENGTH:
            raise ValueError("Invalid word.")
        if self.get(guild_id, user_id, word):
            return False
        async with self._pool.acquire() as conn:
            await _ADD.execute(conn, guild_id, user_id, word)
        self._data[guild_id].setdefault(word, {})[user_id] = Subscription()
        return True

    async def remove(self, guild_id: int, user_id: int, word: str) -> bool:
        """Remove a user's ping; False if there was none."""
        word = normalize(word)
        if not self.get(guild_id, user_id, word):
            return False
        async with self._pool.acquire() as conn:
            await _REMOVE.execute(conn, guild_id, user_id, word)
        users = self._data[guild_id][word]
        del users[user_id]
        if not users:
            del self._data[guild_id][word]
            self._patterns.pop(word, None)
        return True

    async def record_ping(self, guild_id: int, user_id: int, word: str) -> None:
        sub = self.get(guild_id, user_id, word)
        if sub is None:
            return
        sub.count += 1
        async with self._pool.acquire() as conn:
            await _RECORD_PING.execute(conn, guild_id, user_id, normalize(word))

    async def ignore(
        self,
        guild_id: int,
        user_id: int,
        kind: IgnoreKind,
        target_id: int,
        word: str | None = None,
    ) -> int:
        """Ignore a user or channel for one word, or all of the user's words.

        Returns how many words changed.
        """
        return await self._change_ignore(
            guild_id, user_id, kind, target_id, word, add=True
        )

    async def unignore(
        self,
        guild_id: int,
        user_id: int,
        kind: IgnoreKind,
        target_id: int,
        word: str | None = None,
    ) -> int:
        """Stop ignoring a user or channel for one word, or all of the user's words;
        returns how many words changed.
        """
        return await self._change_ignore(
            guild_id, user_id, kind, target_id, word, add=False
        )

    async def _change_ignore(
        self,
        guild_id: int,
        user_id: int,
        kind: IgnoreKind,
        target_id: int,
        word: str | None,
        *,
        add: bool,
    ) -> int:
        mine = self.words_of(guild_id, user_id)
        if word is not None:
            word = normalize(word)
            mine = {word: mine[word]} if word in mine else {}

        changed: list[str] = []
        for w, sub in mine.items():
            ignored = sub.users if kind == "user" else sub.channels
            if (target_id in ignored) == add:
                continue
            changed.append(w)
        if not changed:
            return 0

        async with self._pool.acquire() as conn, conn.transaction():
            if add:
                await _IGNORE.executemany(
                    conn, [(guild_id, user_id, w, kind, target_id) for w in changed]
                )
            else:
                await _UNIGNORE.execute(
                    conn, guild_id, user_id, kind, target_id, changed
                )
        for w in changed:
            sub = mine[w]
            ignored = sub.users if kind == "user" else sub.channels
            (ignored.add if add else ignored.discard)(target_id)
        return len(changed)
