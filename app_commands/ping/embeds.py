from typing import Mapping

import discord


class WordPingsEmbed(discord.Embed):
    def __init__(
        self,
        user: discord.User | discord.Member,
        guild: discord.Guild,
        pings: Mapping[str, dict[str, dict]],
    ) -> None:
        user_id = str(user.id)
        description = ""
        for word in pings:
            if not pings[word][user_id]:
                continue

            count = pings[word][user_id]["count"]
            description += (
                f"`{word}` - pinged `{count}` {("times" if count > 1 else "time")}\n"
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
