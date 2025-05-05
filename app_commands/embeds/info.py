import math
from typing import TYPE_CHECKING

import discord

from app_commands.commons.info import STEP

if TYPE_CHECKING:
    from statics.types import GameDetails


class InfoEmbed(discord.Embed):
    def __init__(
        self,
        game_details: "GameDetails",
        artist: str | None,
        songs: list[list[str]],
        user: discord.User | discord.Member,
        current: int = 1,
        max: int | None = None,
    ) -> None:
        end = current * STEP
        start = end - STEP
        filtered_songs = songs[start:end]
        duration_index = game_details["infoColumns"].index("duration")
        artist_name_index = game_details["infoColumns"].index("artist_name")
        song_name_index = game_details["infoColumns"].index("song_name")

        description = "\n".join(
            f"({song[duration_index]}) "
            f"{(f"{song[artist_name_index].replace(r"*", r"\*").replace(r"_", r"\_")}"
                f" - " if not artist else "")}"
            f"**{song[song_name_index].replace(r"*", r"\*").replace(r"_", r"\_")}**"
            for song in filtered_songs
        )
        super().__init__(
            title=f"{game_details["name"]}{f" - {artist}" if artist else ""}",
            description=description,
            color=game_details["color"],
        )
        self.set_footer(
            text=(
                f"Page {current}/{max or math.ceil(len(songs) / STEP)}"
                f" · Requested by {user.name}"
            ),
        )
