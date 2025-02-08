from typing import Optional, TypedDict


class GameD(TypedDict):
    name: str
    sslId: Optional[str]
    sslRange: Optional[str]
    sslColumns: Optional[list[str]]
    pingId: str
    pingRange: str
    pingWrite: str
    pingColumns: list[str]
    bonusId: str
    bonusRange: str
    bonusColumns: list[str]
    color: int
    pinChannelId: Optional[int]
    api: str
    timezone: str
