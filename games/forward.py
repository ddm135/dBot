"""When a game's next content update starts, as the data tables announce it."""

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .times import ms_to_datetime

WINDOW = timedelta(days=7)


def _starts(table: Mapping[str, Any], timezone: ZoneInfo) -> list[datetime]:
    starts = (
        ms_to_datetime(entry.get("displayStartAt"), timezone)
        for entry in table.values()
        if isinstance(entry, Mapping)
    )
    return [start for start in starts if start is not None]


def next_update(
    tables: Mapping[str, Mapping[str, Any]], timezone: ZoneInfo, now: datetime
) -> datetime | None:
    """The earliest song (else group) that is shown from a moment within a week.

    Songs come first, as in v0: groups only count when no song is about to
    appear.
    """
    for name in ("MusicData", "GroupData"):
        coming = [
            start
            for start in _starts(tables.get(name, {}), timezone)
            if now < start <= now + WINDOW
        ]
        if coming:
            return min(coming)
    return None
