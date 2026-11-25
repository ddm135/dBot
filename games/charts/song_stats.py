"""Song durations and note counts, as written by the asset sync.

They are kept in the database (``db.songstats``), in v0's layout per song:
``{"duration": "3:21", "seq": {difficulty: {...}}}``. The preferred instance
measures and saves them; every instance reads them.
"""

import asyncio
import logging
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SongStat:
    seconds: int | None
    notes: Mapping[str, int] = field(default_factory=dict)  # difficulty -> count

    @property
    def duration(self) -> str:
        return format_duration(self.seconds) if self.seconds is not None else "Unknown"


def format_duration(seconds: float) -> str:
    whole = math.floor(seconds + 0.5)
    return f"{whole // 60}:{whole % 60:02d}"


def parse_duration(text: object) -> int | None:
    """``"3:21"`` to 201 seconds."""
    if not isinstance(text, str):
        return None
    minutes, sep, seconds = text.partition(":")
    try:
        return int(minutes) * 60 + int(seconds) if sep else None
    except ValueError:
        return None


def parse_stats(raw: Mapping[str, Any]) -> dict[int, SongStat]:
    stats: dict[int, SongStat] = {}
    for key, entry in raw.items():
        try:
            code = int(key)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        raw_seq = entry.get("seq")
        seq: dict[str, Any] = raw_seq if isinstance(raw_seq, dict) else {}
        notes = {
            str(level): int(info["count"])
            for level, info in seq.items()
            if isinstance(info, dict) and isinstance(info.get("count"), int)
        }
        seconds = parse_duration(entry.get("duration"))
        if seconds is None:
            lengths = [
                info["duration"]
                for info in seq.values()
                if isinstance(info, dict)
                and isinstance(info.get("duration"), int | float)
            ]
            if lengths:
                seconds = math.floor(min(lengths) + 0.5)
        if seconds is None:
            sound = entry.get("sound")
            seconds = (
                parse_duration(sound.get("duration"))
                if isinstance(sound, dict)
                else None
            )
        stats[code] = SongStat(seconds, notes)
    return stats


class StatsSource(Protocol):
    """Where the stats are kept (the database)."""

    async def version(self, game: str) -> int: ...

    async def load(self, game: str) -> dict[str, Any]: ...


class SongStatsStore:
    """The stats of every game, read from the database.

    The latest are kept in memory. The game's version is looked at (a one-row
    query) at most every ``recheck`` seconds, and the rows are read again only
    when it has changed, so an instance that does not sync still follows the one
    that does.
    """

    def __init__(
        self,
        source: StatsSource,
        *,
        recheck: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._source = source
        self._recheck = recheck
        self._clock = clock
        self._cache: dict[str, tuple[int, float, dict[int, SongStat]]] = {}

    async def get(self, game_key: str) -> Mapping[int, SongStat]:
        """The stats of a game, read again when they have changed. Empty if none."""
        cached = self._cache.get(game_key)
        now = self._clock()
        if cached and now - cached[1] < self._recheck:
            return cached[2]
        try:
            version = await self._source.version(game_key)
            if cached and cached[0] == version:
                self._cache[game_key] = (version, now, cached[2])
                return cached[2]
            raw = await self._source.load(game_key)
            stats = await asyncio.to_thread(parse_stats, raw)
        except Exception:
            logger.warning("Could not read the stats of %s.", game_key, exc_info=True)
            return cached[2] if cached else {}
        self._cache[game_key] = (version, now, stats)
        return stats
