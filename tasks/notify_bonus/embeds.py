from datetime import datetime
from pathlib import Path

import discord

from statics.consts import BONUS_OFFSET


class NotifyBonusEmbed(discord.Embed):
    def __init__(
        self,
        artist_name: str,
        icon: str | Path | None,
        current_date: datetime,
        starts: list[str],
        ends: list[str],
        color: int,
    ) -> None:
        super().__init__(
            color=color,
        )
        self.set_author(
            name=artist_name.replace(r"*", r"\*")
            .replace(r"_", r"\_")
            .replace(r"`", r"\`"),
            icon_url="attachment://icon.png" if isinstance(icon, Path) else icon,
        )

        started = False
        start_length = len(starts)
        i = 0
        while i < start_length:
            start_str = ""
            while i < start_length and len(start_str) + len(starts[i]) < 1024:
                start_str += starts[i]
                i += 1
            self.add_field(
                name=(
                    (
                        f"Available <t:"
                        f"{int(current_date.timestamp())}"
                        f":R> :green_circle:"
                    )
                    if not started
                    else "\u200b"
                ),
                value=start_str,
                inline=False,
            )
            started = True

        ended = False
        end_length = len(ends)
        i = 0
        while i < end_length:
            end_str = ""
            while i < end_length and len(end_str) + len(ends[i]) < 1024:
                end_str += ends[i]
                i += 1
            self.add_field(
                name=(
                    (
                        f"Ends <t:"
                        f"{int((current_date + BONUS_OFFSET).timestamp())}"
                        f":R> :orange_circle:"
                    )
                    if not ended
                    else "\u200b"
                ),
                value=end_str,
                inline=False,
            )
            ended = True
