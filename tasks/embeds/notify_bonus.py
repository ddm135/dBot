from datetime import datetime

import discord

from statics.consts import BONUS_OFFSET


class NotifyEmbed(discord.Embed):
    def __init__(
        self,
        artist: str,
        icon_url: str | None,
        current_date: datetime,
        starts: list[str],
        ends: list[str],
        color: int,
    ) -> None:
        super().__init__(color=color)
        self.set_author(
            name=artist.replace(r"*", r"\*").replace(r"_", r"\_"), icon_url=icon_url
        )

        if starts:
            self.add_field(
                name=(
                    f"Available <t:"
                    f"{int(current_date.timestamp())}"
                    f":R> :green_circle:"
                ),
                value="".join(starts),
                inline=False,
            )
        if ends:
            self.add_field(
                name=(
                    f"Ends <t:"
                    f"{int((current_date + BONUS_OFFSET).timestamp())}"
                    f":R> :orange_circle:"
                ),
                value="".join(ends),
                inline=False,
            )
