from collections import defaultdict
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from statics.types import PingDetails


class WordPingsEmbed(discord.Embed):
    def __init__(
        self,
        user: discord.User | discord.Member,
        guild: discord.Guild,
        pings: defaultdict[str, defaultdict[str, "PingDetails"]],
    ) -> None:
        user_id = str(user.id)
        description = ""
        for word in pings:
            if not pings[word][user_id]:
                continue

            description += (
                f"`{word}` - pinged `{pings[word][user_id].setdefault("count", 0)}`"
                f" {("times" if pings[word][user_id]["count"] > 1 else "time")}\n"
            )

        if not description:
            description = "None"
        else:
            description = description[:-1]

        super().__init__(
            description=description,
            color=user.color,
        )
        self.set_author(
            name=f"Word Pings in {guild.name}",
            icon_url=guild.icon.url if guild.icon else None,
        )
