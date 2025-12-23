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
        artist_name: str | None,
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
            title=(
                artist_name.replace(r"*", r"\*")
                .replace(r"_", r"\_")
                .replace(r"`", r"\`")
                if artist_name
                else "All Songs"
            ),
            description="\n".join(
                f"({info[song[song_id_index]]["sound"]["duration"]}) "
                f"{(f"{song[artist_name_index].replace(r"*", r"\*").replace(r"_", r"\_")
                    .replace(r"`", r"\`")} - " if not artist_name else "")}"
                f"**{(song[song_name_index].replace(r"*", r"\*").replace(r"_", r"\_")
                      .replace(r"`", r"\`"))}**"
                for song in filtered_songs
            ),
            color=game_details["color"],
        )
        self.set_author(
            name=f"{game_details["name"]} - Song Length",
            icon_url=(
                f"attachment://{icon.name.replace(r"'", r"")}"
                if isinstance(icon, Path)
                else icon
            ),
        )
        self.set_footer(
            text=f"Page {current_page}/{max_page or math.ceil(len(songs) / STEP)}",
        )


class InfoDetailsEmbed(discord.Embed):
    def __init__(
        self,
        game: str,
        artist_name: str,
        song_name: str,
        duration: str,
        note_count: dict,
        album: str | Path | None,
        icon: str | Path | None,
        color: int,
        album_info: dict[str, str],
        skills: str | None,
        my_record: int,
    ) -> None:
        print(album)
        print(icon)
        game_details = GAMES[game]
        super().__init__(
            title=artist_name.replace(r"*", r"\*")
            .replace(r"_", r"\_")
            .replace(r"`", r"\`"),
            description=f"**{(song_name.replace(r"*", r"\*").replace(r"_", r"\_")
                              .replace(r"`", r"\`"))}**",
            color=color,
        )

        self.set_author(
            name=f"{game_details["name"]} - Song Info",
            icon_url=(
                f"attachment://{icon.name.replace(r"'", r"")}"
                if isinstance(icon, Path)
                else icon
            ),
        )
        self.set_thumbnail(
            url=(
                f"attachment://{album.name.replace(r"'", r"")}"
                if isinstance(album, Path)
                else album
            )
        )

        self.add_field(name="Duration", value=duration)
        if (
            (
                difficulty_levels := " / ".join(
                    difficulty for difficulty in note_count.keys()
                )
            )
        ) != "Easy / Normal / Hard":
            self.add_field(name="Difficulty Levels", value=difficulty_levels)
        self.add_field(
            name="Note Count",
            value=" / ".join(
                str(difficulty["count"]) for difficulty in note_count.values()
            ),
        )
        if skills:
            self.add_field(name="Skill Order", value=skills, inline=False)

        self.add_field(
            name="Album",
            value=album_info["album_name"]
            .replace(r"*", r"\*")
            .replace(r"_", r"\_")
            .replace(r"`", r"\`"),
            inline=False,
        )
        self.add_field(
            name="Release Date",
            value=album_info["release_date"],
        )
        self.add_field(
            name="My Record Challenge Score",
            value=f"{my_record:,}",
        )
