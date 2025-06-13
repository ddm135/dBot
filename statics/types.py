import random
import string
from datetime import datetime
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


class SSLeagueEmbed(discord.Embed):
    def __init__(
        self,
        artist_name: str,
        song_name: str,
        duration: str,
        image_url: str | None,
        color: int,
        skills: str | None,
        current_time: datetime,
        user_name: str,
        artist_last: datetime | None = None,
        song_last: datetime | None = None,
    ) -> None:
        super().__init__(
            color=color,
            title=f"SSL #{current_time.strftime("%u")}",
            description=(
                f"**{artist_name.replace(r"*", r"\*").replace(r"_", r"\_")} - "
                f"{song_name.replace(r"*", r"\*").replace(r"_", r"\_")}**"
            ),
        )

        self.add_field(
            name="Duration",
            value=duration,
            inline=True if skills else False,
        )
        if skills:
            self.add_field(
                name="Skill Order",
                value=skills,
            )
        self.add_field(
            name="Artist Last Appearance",
            value=(
                artist_last.strftime("%A, %B %d, %Y").replace(" 0", " ")
                if artist_last
                else "N/A"
            ),
        )
        self.add_field(
            name="Song Last Appearance",
            value=(
                song_last.strftime("%A, %B %d, %Y").replace(" 0", " ")
                if song_last
                else "N/A"
            ),
        )

        self.set_thumbnail(url=image_url)
        self.set_footer(
            text=(
                f"{current_time.strftime("%A, %B %d, %Y").replace(" 0", " ")}"
                f" · Pinned by {user_name}"
            )
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
    manifest: str
    api: str
    authorization: str
    target_audience: str
    legacyUrlScheme: bool


class LastAppearance(TypedDict):
    songs: dict[str, str | None]
    date: str | None


PinataDetails = TypedDict(
    "PinataDetails",
    {"role": discord.Role | str, "from": str, "mention": str, "label": str},
)
