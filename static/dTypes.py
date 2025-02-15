from datetime import timedelta
from typing import Optional, TypedDict
from zoneinfo import ZoneInfo


class GameDetails(TypedDict):
    name: str
    sslId: Optional[str]
    sslRange: Optional[str]
    sslColumns: Optional[list[str]]
    sslOffset: Optional[timedelta]
    pingId: str
    pingRange: str
    pingWrite: str
    pingColumns: list[str]
    bonusId: str
    bonusRange: str
    bonusColumns: list[str]
    color: int
    pinChannelIds: Optional[dict[int, int]]
    api: str
    timezone: ZoneInfo
