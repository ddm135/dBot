# pyright: reportTypedDictNotRequiredAccess=false

import math
from pathlib import Path

import discord

from statics.consts import GAMES

from .commons import STEP


class InfoEmbed(discord.Embed):
    def __init__(
        self,
        game: str,
        artist: str | None,
        songs: list[list[str]],
        info: dict[str, dict[str, dict[str, str]]],
        icon: str | Path | None,
        current_page: int = 1,
        max_page: int | None = None,
    ) -> None:
        game_details = GAMES[game]
        end = current_page * STEP
        start = end - STEP
        filtered_songs = songs[start:end]
        info_columns = game_details["info"]["columns"]
        song_id_index = info_columns.index("song_id")
        artist_name_index = info_columns.index("artist_name")
        song_name_index = info_columns.index("song_name")

        super().__init__(
            title="Songs",
            description="\n".join(
                f"({info[song[song_id_index]]["sound"]["duration"]}) "
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
                f"attachment://{icon.name.replace(r"'", r"")}"
                if isinstance(icon, Path)
                else icon
            ),
        )
        self.set_footer(
            text=f"Page {current_page}/{max_page or math.ceil(len(songs) / STEP)}",
        )
