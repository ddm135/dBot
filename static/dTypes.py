from datetime import timedelta
from typing import TypedDict
from zoneinfo import ZoneInfo


class GameDetails(TypedDict):
    name: str
    infoId: str
    infoSongs: str
    infoColumns: tuple[str, ...]
    pingId: str
    pingRange: str
    pingWrite: str
    pingColumns: tuple[str, ...]
    bonusId: str
    bonusRange: str
    bonusColumns: tuple[str, ...]
    color: int
    pinChannelIds: dict[int, int | None]
    pinRoles: dict[int, int | None]
    api: str
    dateFormat: str
    timezone: ZoneInfo
    resetOffset: timedelta
