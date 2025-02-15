from datetime import timedelta
from typing import Optional, TypedDict
from zoneinfo import ZoneInfo


class GameDetails(TypedDict):
    name: str
    sslId: Optional[str]
    sslRange: Optional[str]
    sslColumns: Optional[tuple[str, ...]]
    sslOffset: Optional[timedelta]
    pingId: str
    pingRange: str
    pingWrite: str
    pingColumns: tuple[str, ...]
    bonusId: str
    bonusRange: str
    bonusColumns: tuple[str, ...]
    color: int
    pinChannelIds: Optional[dict[int, int]]
    api: str
    timezone: ZoneInfo
