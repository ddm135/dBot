# pyright: reportTypedDictNotRequiredAccess=false

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
        icon: str | discord.File | None,
        current_page: int = 1,
        max_page: int | None = None,
    ) -> None:
        end = current_page * STEP
        start = end - STEP
        filtered_songs = songs[start:end]
        info_columns = game_details["info"]["columns"]
        duration_index = info_columns.index("duration")
        artist_name_index = info_columns.index("artist_name")
        song_name_index = info_columns.index("song_name")

        super().__init__(
            title="Songs",
            description="\n".join(
                f"({song[duration_index]}) "
                f"{(f"{song[artist_name_index].replace(r"*", r"\*").replace(r"_", r"\_")
                    .replace(r"`", r"\`")} - " if not artist else "")}"
                f"**{(song[song_name_index].replace(r"*", r"\*").replace(r"_", r"\_")
                      .replace(r"`", r"\`"))}**"
                for song in filtered_songs
            ),
            color=game_details["color"],
        )
        self.set_author(
            name=f"{game_details["name"]}{f" - {artist}" if artist else ""}",
            icon_url=(
                f"attachment://{icon.filename}"
                if isinstance(icon, discord.File)
                else icon
            ),
        )
        self.set_footer(
            text=f"Page {current_page}/{max_page or math.ceil(len(songs) / STEP)}",
        )
