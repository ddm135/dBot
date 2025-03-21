from datetime import timedelta
from typing import Optional, TypedDict
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
    pinChannelIds: Optional[dict[int, int]]
    pinRoles: Optional[dict[int, Optional[int]]]
    api: str
    dateFormat: str
    timezone: ZoneInfo
    resetOffset: timedelta
