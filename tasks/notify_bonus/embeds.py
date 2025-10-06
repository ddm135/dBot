from datetime import datetime
from pathlib import Path

import discord

from statics.consts import BONUS_OFFSET


class NotifyBonusEmbed(discord.Embed):
    def __init__(
        self,
        artist: str,
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
            name=artist.replace(r"*", r"\*").replace(r"_", r"\_").replace(r"`", r"\`"),
            icon_url=(
                f"attachment://{icon.name.replace(r"'", r"")}"
                if isinstance(icon, Path)
                else icon
            ),
        )

        started = False
        while starts:
            start_str = ""
            while starts and len(start_str) + len(starts[0]) < 1024:
                start_str += starts.pop(0)
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
        while ends:
            end_str = ""
            while ends and len(end_str) + len(ends[0]) < 1024:
                end_str += ends.pop(0)
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
