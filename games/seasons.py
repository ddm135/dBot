"""World-record seasons.

Most games have quarterly seasons, listed in the ``WorldRecordData`` table.
Weekly games number a season by the Monday it starts (``20241202``).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .decks import Entry
from .times import ms_to_datetime


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
