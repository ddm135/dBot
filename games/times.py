"""Timestamps from the game data: milliseconds since the epoch."""

from datetime import date, datetime
from zoneinfo import ZoneInfo


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
