"""Import the JSON files of v0 into Postgres.

The parsing is pure (it only reads dicts) so it can be tested; :func:`import_all`
writes the result. Importing twice is safe.
"""

import logging
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import asyncpg

from .bonus_pings import IMPORT_PREFERENCES, IMPORT_SUBSCRIPTION
from .misc import INSERT_CREDENTIAL_IF_NEW, INSERT_LIVE_THEME_IF_NEW
from .roles import INSERT_IGNORING
from .ssl import INSERT_MISSING
from .word_pings import IMPORT_IGNORE, IMPORT_PING, normalize

logger = logging.getLogger(__name__)

type DeckLookup = Callable[[str, str], int | None]  # (game, artist name) -> deck code
type SongLookup = Callable[[str, int], int | None]  # (game, song code) -> deck code
type DateParser = Callable[[str, str], date | None]  # (game, text) -> date


# Keys v0 stored next to the artist names of a game; they are not artists.
JUNK_KEYS = frozenset({"start", "end", "restart", "reend"})


@dataclass(slots=True)
class WordPing:
    count: int = 0
    users: set[int] = field(default_factory=set)
    channels: set[int] = field(default_factory=set)


@dataclass(slots=True)
class Report:
    imported: dict[str, int] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)

    def add(self, what: str, count: int) -> None:
        self.imported[what] = self.imported.get(what, 0) + count


def _int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[call-overload, no-any-return]
    except TypeError, ValueError:
        return None


def parse_word_pings(data: Mapping[str, Any]) -> dict[tuple[int, int, str], WordPing]:
    """``{guild: {word: {user: {users, channels, count}}}}``.

    Words are case-insensitive now, so "Cat" and "cat" are merged.
    """
    result: dict[tuple[int, int, str], WordPing] = defaultdict(WordPing)
    for guild, words in data.items():
        guild_id = _int(guild)
        if guild_id is None or not isinstance(words, dict):
            continue
        for word, users in words.items():
            key_word = normalize(word)
            if not key_word or len(key_word) > 100 or not isinstance(users, dict):
                continue
            for user, info in users.items():
                user_id = _int(user)
                if user_id is None or not isinstance(info, dict) or not info:
                    continue  # v0 left empty entries behind for removed users
                ping = result[(guild_id, user_id, key_word)]
                ping.count += _int(info.get("count")) or 0
                ping.users |= {
                    u for x in info.get("users", []) if (u := _int(x)) is not None
                }
                ping.channels |= {
                    c for x in info.get("channels", []) if (c := _int(x)) is not None
                }
    return dict(result)


def parse_roles(data: Mapping[str, Any]) -> set[tuple[int, int]]:
    pairs: set[tuple[int, int]] = set()
    for user, roles in data.items():
        user_id = _int(user)
        if user_id is None or not isinstance(roles, list):
            continue
        pairs |= {(user_id, r) for x in roles if (r := _int(x)) is not None}
    return pairs


def parse_live_themes(
    data: Mapping[str, Any], games: set[str]
) -> dict[tuple[int, str], int]:
    """Either ``{user: {game: amount}}`` or ``{game: {user: amount}}``."""
    result: dict[tuple[int, str], int] = {}
    for outer, inner in data.items():
        if not isinstance(inner, dict):
            continue
        for key, amount in inner.items():
            game, user = (outer, key) if outer in games else (key, outer)
            user_id, value = _int(user), _int(amount)
            if game in games and user_id is not None and value:
                result[(user_id, game)] = value
    return result


@dataclass(slots=True)
class BonusPingData:
    subscriptions: set[tuple[int, str, int]] = field(default_factory=set)
    preferences: dict[int, tuple[int, int]] = field(default_factory=dict)


def parse_notify_bonus(
    data: Mapping[str, Any], games: set[str], deck_of: DeckLookup, report: Report
) -> BonusPingData:
    """``{game: {artist: [users]}, user: {start, end, restart, reend}}``."""
    result = BonusPingData()
    unmatched: dict[str, list[str]] = {}
    for key, value in data.items():
        if key in games and isinstance(value, dict):
            for artist, users in value.items():
                if artist in JUNK_KEYS:  # v0's defaultdicts left these behind
                    continue
                deck = deck_of(key, artist)
                if deck is None:
                    unmatched.setdefault(key, []).append(artist)
                    continue
                for x in users if isinstance(users, list) else []:
                    if (user_id := _int(x)) is not None:
                        result.subscriptions.add((user_id, key, deck))
        elif (user_id := _int(key)) is not None and isinstance(value, dict):
            # The "re" values are what the user asked for last; the others are
            # what applies today. Prefer the request.
            def hours(*names: str, value: dict[str, Any] = value) -> int | None:
                for name in names:
                    got = value.get(name)
                    if (
                        isinstance(got, list)
                        and got
                        and (h := _int(got[0])) is not None
                    ):
                        return h
                return None

            start, end = hours("restart", "start"), hours("reend", "end")
            result.preferences[user_id] = (
                min(max(1 if start is None else start, 0), 23),
                min(max(1 if end is None else end, 0), 23),
            )
    for game, names in unmatched.items():
        report.skipped.append(
            f"bonus pings: {game}: no deck named " + ", ".join(repr(n) for n in names)
        )
    return result


def parse_ssleagues(
    data: Mapping[str, Any],
    deck_of: DeckLookup,
    deck_of_song: SongLookup,
    parse_date: DateParser,
    report: Report,
) -> dict[tuple[str, date], tuple[int, int]]:
    """``{game: {artist: {date, songs: {song: date}}}}`` to one row per day."""
    rows: dict[tuple[str, date], tuple[int, int]] = {}
    for game, artists in data.items():
        if not isinstance(artists, dict):
            continue
        for artist, info in artists.items():
            if not isinstance(info, dict):
                continue
            songs = info.get("songs") or {}
            for song, text in songs.items() if isinstance(songs, dict) else []:
                code = _int(song)
                day = parse_date(game, text) if isinstance(text, str) else None
                if code is None or day is None:
                    continue
                deck = deck_of_song(game, code) or deck_of(game, artist)
                if deck is None:
                    report.skipped.append(
                        f"ssl: {game} song {code} ({artist!r}) has no deck"
                    )
                    continue
                rows[(game, day)] = (code, deck)
    return rows


async def import_all(
    pool: asyncpg.Pool,
    v0: Mapping[str, Mapping[str, Any]],
    *,
    games: set[str],
    deck_of: DeckLookup,
    deck_of_song: SongLookup,
    parse_date: DateParser,
) -> Report:
    """Write v0's files to the database. ``v0`` maps a file stem to its content."""
    report = Report()
    async with pool.acquire() as conn, conn.transaction():
        if creds := v0.get("credentials"):
            valid = {
                g: c for g, c in creds.items() if g in games and isinstance(c, dict)
            }
            await INSERT_CREDENTIAL_IF_NEW.executemany(conn, list(valid.items()))
            report.add("credentials", len(valid))

        pings = parse_word_pings(v0.get("word_pings", {}))
        await IMPORT_PING.executemany(
            conn, [(g, u, w, p.count) for (g, u, w), p in pings.items()]
        )
        ignores = [
            (g, u, w, kind, target)
            for (g, u, w), p in pings.items()
            for kind, targets in (("user", p.users), ("channel", p.channels))
            for target in targets
        ]
        await IMPORT_IGNORE.executemany(conn, ignores)
        report.add("word pings", len(pings))
        report.add("word ping ignores", len(ignores))

        roles = parse_roles(v0.get("roles", {}))
        await INSERT_IGNORING.executemany(conn, sorted(roles))
        report.add("stored roles", len(roles))

        themes = parse_live_themes(v0.get("live_theme", {}), games)
        await INSERT_LIVE_THEME_IF_NEW.executemany(
            conn, [(u, g, a) for (u, g), a in themes.items()]
        )
        report.add("live themes", len(themes))

        notify = parse_notify_bonus(v0.get("notify_bonus", {}), games, deck_of, report)
        await IMPORT_SUBSCRIPTION.executemany(conn, sorted(notify.subscriptions))
        await IMPORT_PREFERENCES.executemany(
            conn, [(u, s, e) for u, (s, e) in notify.preferences.items()]
        )
        report.add("bonus subscriptions", len(notify.subscriptions))
        report.add("bonus preferences", len(notify.preferences))

        ssl = parse_ssleagues(
            v0.get("ssleagues", {}), deck_of, deck_of_song, parse_date, report
        )
        await INSERT_MISSING.executemany(
            conn, [(g, d, s, k) for (g, d), (s, k) in ssl.items()]
        )
        report.add("ssl days", len(ssl))
    return report
