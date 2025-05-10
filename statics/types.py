import random
import string
from typing import TypedDict
from zoneinfo import ZoneInfo

import discord

from statics.consts import IV_LENGTH


class SuperStarHeaders(dict):
    def __init__(self) -> None:
        super().__init__(
            {
                "X-SuperStar-AES-IV": "".join(
                    random.choices(string.ascii_uppercase, k=IV_LENGTH)
                ),
                "X-SuperStar-Asset-Ignore": "true",
                "X-SuperStar-API-Version": "8",
            }
        )


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
