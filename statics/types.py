from datetime import timedelta
from typing import TypedDict
from zoneinfo import ZoneInfo

import discord


class GameDetails(TypedDict):
    name: str
    infoId: str
    infoRange: str
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
    dateFormat: str
    timezone: ZoneInfo
    resetOffset: timedelta
    api: str
    legacyUrlScheme: bool


class PingDetails(TypedDict):
    users: list[int]
    channels: list[int]
    count: int


PinataDetails = TypedDict(
    "PinataDetails",
    {"role": discord.Role | str, "from": str, "mention": str, "label": str},
)
