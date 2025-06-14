import math
from typing import TYPE_CHECKING

import discord

from .commons import STEP

if TYPE_CHECKING:
    from statics.types import GameDetails


class InfoEmbed(discord.Embed):
    def __init__(
        self,
        game_details: "GameDetails",
        artist: str | None,
        songs: list[list[str]],
        current_page: int = 1,
        max_page: int | None = None,
    ) -> None:
        end = current_page * STEP
        start = end - STEP
        filtered_songs = songs[start:end]
        duration_index = game_details["infoColumns"].index("duration")
        artist_name_index = game_details["infoColumns"].index("artist_name")
        song_name_index = game_details["infoColumns"].index("song_name")

        super().__init__(
            title=f"{game_details["name"]}{f" - {artist}" if artist else ""} Songs",
            description="\n".join(
                f"({song[duration_index]}) "
                f"{(f"{song[artist_name_index].replace(r"*", r"\*")
                    .replace(r"_", r"\_")} - " if not artist else "")}"
                f"**{song[song_name_index].replace(r"*", r"\*").replace(r"_", r"\_")}**"
                for song in filtered_songs
            ),
            color=game_details["color"],
        )
        self.set_footer(
            text=f"Page {current_page}/{max_page or math.ceil(len(songs) / STEP)}",
        )
