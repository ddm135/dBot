"""Dates from the game data: timestamps, when the next content update starts, and world-record seasons."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from games.models import Entry


def ms_to_datetime(value: object, timezone: ZoneInfo) -> datetime | None:
    """A timestamp in the game's timezone; None if it is not a usable number."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        return datetime.fromtimestamp(value / 1000, timezone)
    except OverflowError, OSError, ValueError:
        return None


def ms_to_date(value: object, timezone: ZoneInfo) -> date | None:
    """The calendar date of a timestamp in the game's timezone."""
    moment = ms_to_datetime(value, timezone)
    return moment.date() if moment else None


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


@dataclass(frozen=True, slots=True)
class Season:
    code: int
    start: datetime
    end: datetime


def quarterly_seasons(
    tables: Mapping[str, Mapping[str, Entry]], timezone: ZoneInfo, now: datetime
) -> dict[int, Season]:
    """The quarterly seasons that have started, oldest first.

    The table has a row per reward tier, so a season appears several times.
    """
    seasons: dict[int, Season] = {}
    for row in tables.get("WorldRecordData", {}).values():
        code = row.get("seasonCode")
        started = ms_to_datetime(row.get("startAt"), timezone)
        ended = ms_to_datetime(row.get("endAt"), timezone)
        if (
            not isinstance(code, int)
            or isinstance(code, bool)
            or code in seasons
            or started is None
            or ended is None
            or started > now
        ):
            continue
        seasons[code] = Season(code, started, ended)
    return dict(sorted(seasons.items()))


def latest_season(seasons: Mapping[int, Season]) -> int | None:
    return max(seasons) if seasons else None


def season_code_of(day: date) -> int:
    """``2024-12-02`` as ``20241202``."""
    return day.year * 10000 + day.month * 100 + day.day


def current_monday(today: date) -> date:
    return today - timedelta(days=today.weekday())


class SeasonError(ValueError):
    """A weekly season code that cannot be used; the message says why."""


def check_weekly(code: int, first: date, today: date) -> date:
    """The Monday a weekly season code stands for, or raise :class:`SeasonError`."""
    try:
        day = datetime.strptime(str(code), "%Y%m%d").date()
    except ValueError:
        raise SeasonError("Season code must be a date as YYYYMMDD.") from None
    if day.weekday():
        raise SeasonError("Season code must be a Monday.")
    if day > today:
        raise SeasonError("Season code cannot be in the future.")
    if day < first:
        raise SeasonError("Season code is before the first season.")
    return day
