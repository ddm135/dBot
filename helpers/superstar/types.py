import random
import string
from datetime import datetime

import discord

from .commons import API_VERSION, ASSET_IGNORE, IV_LENGTH


class SuperStarHeaders(dict):
    def __init__(self) -> None:
        super().__init__(
            {
                "X-SuperStar-AES-IV": "".join(
                    random.choices(string.ascii_uppercase, k=IV_LENGTH)
                ),
                "X-SuperStar-Asset-Ignore": ASSET_IGNORE,
                "X-SuperStar-API-Version": API_VERSION,
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
        )
        if skills:
            self.add_field(
                name="Skill Order",
                value=skills,
            )

        self.add_field(
            name="Artist Last Appearance",
            value=(
                f"{artist_last.strftime("%A, %B %d, %Y").replace(" 0", " ")} "
                f"(<t:{int(artist_last.timestamp())}:R>)"
                if artist_last is not None
                else "N/A"
            ),
            inline=False,
        )
        self.add_field(
            name="Song Last Appearance",
            value=(
                f"{song_last.strftime("%A, %B %d, %Y").replace(" 0", " ")} "
                f"(<t:{int(song_last.timestamp())}:R>)"
                if song_last is not None
                else "N/A"
            ),
            inline=False,
        )

        self.set_thumbnail(url=image_url)
        self.set_footer(
            text=(
                f"{current_time.strftime("%A, %B %d, %Y").replace(" 0", " ")}"
                f" · Pinned by {user_name}"
            )
        )
