"""Song durations and note counts, kept for every instance to read.

One row per song (``data`` is v0's per-song document: ``{"duration": "3:21",
"seq": {difficulty: {...}}}``) and a version per game that goes up with every
save, so a reader can tell cheaply whether it has the latest.
"""

import asyncio
import json
from collections.abc import Iterable, Mapping
from typing import Any, NamedTuple

import asyncpg
from asyncpg_typed import RequiredJsonType, sql


class _Row(NamedTuple):
    song: int
    data: str  # the document as JSON text; decoded in a thread (see ``load``)


_VERSION = sql(
    t"SELECT version FROM song_stats_versions WHERE game = {1}",
    arg=str,
    result=int,
)

_LOAD = sql(
    t"SELECT song, data::text FROM song_stats WHERE game = {1}",
    arg=str,
    resultset=_Row,
)

_SAVE_SONG = sql(
    t"INSERT INTO song_stats (game, song, data) VALUES ({1}, {2}, {3}) "
    t"ON CONFLICT (game, song) DO UPDATE SET data = EXCLUDED.data",
    args=tuple[str, int, RequiredJsonType],
)

_BUMP_VERSION = sql(
    t"INSERT INTO song_stats_versions (game, version) VALUES ({1}, 1) "
    t"ON CONFLICT (game) DO UPDATE SET version = song_stats_versions.version + 1",
    arg=str,
)


class SongStatsDb:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        # What each game's rows hold, as text, so only changed songs are written.
        self._saved: dict[str, dict[int, str]] = {}

    async def version(self, game: str) -> int:
        """Goes up whenever the game's stats are saved; 0 if never."""
        async with self._pool.acquire() as conn:
            row = await _VERSION.fetchrow(conn, game)
        return row[0] if row else 0

    async def load(self, game: str) -> dict[str, Any]:
        """The game's stored songs, as ``{song code: document}``."""
        async with self._pool.acquire() as conn:
            rows = await _LOAD.fetch(conn, game)
        # A game has thousands of songs: decoding them is more than a second of
        # CPU, which must not hold the event loop.
        found, saved = await asyncio.to_thread(_decode, rows)
        self._saved[game] = saved
        return found

    async def save(self, game: str, songs: Mapping[str, Any]) -> int:
        """Write the songs that changed since the last load or save; returns how many."""
        saved = self._saved.setdefault(game, {})
        changed: list[tuple[str, int, Any]] = []
        for key, document in songs.items():
            if not key.isdigit() or not isinstance(document, dict):
                continue
            text = _text(document)
            if saved.get(int(key)) != text:
                changed.append((game, int(key), document))
                saved[int(key)] = text
        if not changed:
            return 0
        async with self._pool.acquire() as conn, conn.transaction():
            await _SAVE_SONG.executemany(conn, changed)
            await _BUMP_VERSION.execute(conn, game)
        return len(changed)


def _decode(rows: Iterable[_Row]) -> tuple[dict[str, Any], dict[int, str]]:
    """``{song code: document}`` and what each document is as text."""
    found: dict[str, Any] = {}
    saved: dict[int, str] = {}
    for row in rows:
        document = json.loads(row.data)
        if isinstance(document, dict):
            found[str(row.song)] = document
            saved[row.song] = _text(document)
    return found, saved


def _text(document: Any) -> str:
    return json.dumps(document, sort_keys=True)
