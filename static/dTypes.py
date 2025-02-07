from typing import TypedDict


class GameD(TypedDict):
    name: str
    sslId: str
    sslRange: str
    sslColumns: list[str]
    pingId: str
    pingRange: str
    pingWrite: str
    pingColumns: list[str]
    bonusId: str
    bonusRange: str
    bonusColumns: list[str]
    color: int
    pinChannelId: int
    api: str
    timezone: str
