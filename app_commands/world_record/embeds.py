import math
from datetime import datetime
from pathlib import Path

import discord

from statics.consts import GAMES

from .commons import STEP


class SongWorldRecordEmbed(discord.Embed):
    def __init__(
        self,
        game: str,
        artist_name: str,
        song_name: str,
        season_code: int,
        start_date: datetime,
        end_date: datetime,
        world_records: list[dict],
        last_updated: datetime | None,
        icon: str | Path | None,
        current_page: int = 1,
        max_page: int | None = None,
    ) -> None:
        game_details = GAMES[game]
        end = current_page * STEP
        start = end - STEP
        filtered_records = world_records[start:end]

        super().__init__(
            title=(
                f"{artist_name.replace(r"*", r"\*").replace(r"_", r"\_")
                   .replace(r"`", r"\`")} - "
                f"{song_name.replace(r"*", r"\*").replace(r"_", r"\_")
                   .replace(r"`", r"\`")}"
            ),
            description=(
                "\n".join(
                    f"{record.get("rank", 1)}. **"
                    f"{record["nickname"].replace(r'*', r'\*')
                       .replace(r'_', r'\_').replace(r'`', r'\`')}"
                    f"** - {record["highscore"]:,}"
                    for record in filtered_records
                )
                if filtered_records
                else "None"
            ),
            color=game_details["color"],
        )

        self.set_author(
            name=(
                f"{game_details["name"]} - WR Season {season_code} "
                f"({start_date.strftime(game_details["dateFormat"])} - "
                f"{end_date.strftime(game_details["dateFormat"])})"
            ),
            icon_url="attachment://icon.png" if isinstance(icon, Path) else icon,
        )
        self.set_footer(
            text=(
                f"Page {current_page}/"
                f"{max_page or math.ceil(len(world_records) / STEP) or 1}"
                f"{last_updated.strftime(
                    f" · Last Updated: %A, %B %d, %Y, %H:%M:%S "
                    f"{game_details["timezone"]}"
                ).replace(" 0", " ") if last_updated else ""}"
            )
        )


class ArtistWorldRecordEmbed(discord.Embed):
    def __init__(
        self,
        game: str,
        artist_name: str,
        season_code: int,
        start_date: datetime,
        end_date: datetime,
        world_records: dict[str, dict | str],
        last_updated: datetime | None,
        icon: str | Path | None,
        current_page: int = 1,
        max_page: int | None = None,
    ) -> None:
        game_details = GAMES[game]
        end = current_page * STEP
        start = end - STEP
        filtered_records = {
            song: record
            for i, (song, record) in enumerate(world_records.items())
            if start <= i < end
        }

        super().__init__(
            title=(
                f"{artist_name.replace(r"*", r"\*").replace(r"_", r"\_")
                   .replace(r"`", r"\`")}"
            ),
            description=(
                "\n".join(
                    f"- {song.replace(r"*", r"\*").replace(r"_", r"\_")
                         .replace(r"`", r"\`")}: "
                    f"{record if isinstance(record, str)
                        else f"{record["nickname"].replace(r"*", r"\*")
                                .replace(r"_", r"\_")
                                .replace(r"`", r"\`")} - {record["highscore"]:,}"}"
                    for song, record in filtered_records.items()
                )
                if filtered_records
                else "None"
            ),
            color=game_details["color"],
        )

        self.set_author(
            name=(
                f"{game_details["name"]} - WR Season {season_code} "
                f"({start_date.strftime(game_details["dateFormat"])} - "
                f"{end_date.strftime(game_details["dateFormat"])})"
            ),
            icon_url="attachment://icon.png" if isinstance(icon, Path) else icon,
        )
        self.set_footer(
            text=(
                f"Page {current_page}/"
                f"{max_page or math.ceil(len(world_records) / STEP) or 1}"
                f"{last_updated.strftime(
                    f" · Last Updated: %A, %B %d, %Y, %H:%M:%S "
                    f"{game_details["timezone"]}"
                ).replace(" 0", " ") if last_updated else ""}"
            )
        )
