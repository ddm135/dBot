import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from app_commands.world_record.embeds import (
    ArtistWorldRecordEmbed,
    SongWorldRecordEmbed,
)
from app_commands.world_record.views import ArtistWorldRecordView, SongWorldRecordView
from statics.consts import GAMES

from .autocompletes import artist_autocomplete, season_autocomplete, song_autocomplete

if TYPE_CHECKING:
    from dBot import dBot
    from helpers.superstar import SuperStar


class WorldRecord(commands.GroupCog, name="world_record"):
    QUARTERLY_CHOICES = [
        app_commands.Choice(name=game_details["name"], value=game)
        for game, game_details in GAMES.items()
        if not {"firstSeason"} <= set(game_details)
    ]
    WEEKLY_CHOICES = [
        app_commands.Choice(name=game_details["name"], value=game)
        for game, game_details in GAMES.items()
        if {"firstSeason"} <= set(game_details)
    ]

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    @app_commands.command(name="quarterly")
    @app_commands.choices(game_choice=QUARTERLY_CHOICES)
    @app_commands.autocomplete(artist_choice=artist_autocomplete)
    @app_commands.autocomplete(song_choice=song_autocomplete)
    @app_commands.autocomplete(season_code=season_autocomplete)
    @app_commands.rename(
        game_choice="game",
        artist_choice="artist",
        song_choice="song",
        season_code="season",
    )
    async def quarterly(
        self,
        itr: discord.Interaction["dBot"],
        game_choice: app_commands.Choice[str],
        artist_choice: str,
        song_choice: str | None = None,
        season_code: int | None = None,
    ) -> None:
        """View world records for games that follow
        the quarterly season system.
        If song name is provided, view the Top 100,
        else view the Top 1 for all songs.

        Parameters
        -----------
        game_choice: Choice[:class:`str`]
            Game
        artist_choice: :class:`str`
            Artist/Album
        song_choice: Optional[:class:`str`]
            Song (requires artist/album to be set)
        season_code: Optional[:class:`int`]
            Season code (defaults to latest season)
        """

        await itr.response.defer()
        if not (
            songs := (
                self.bot.info_by_name[game_choice.value].get(artist_choice, {}).values()
            )
        ):
            return await itr.followup.send("Artist not found.")
        icon = self.bot.artist[game_choice.value][artist_choice]["emblem"]

        if season_code is None:
            season_code = max(self.bot.world_record[game_choice.value])
        elif season_code not in self.bot.world_record[game_choice.value]:
            return await itr.followup.send("Season not found.")

        game_details = GAMES[game_choice.value]
        info_columns = game_details["spreadsheet"]["columns"][0]
        song_id_index = info_columns.index("song_id")
        cog: "SuperStar" = self.bot.get_cog(
            "SuperStar",
        )  # type: ignore[assignment]

        if song_choice:
            if not (
                song := self.bot.info_by_name[game_choice.value]
                .get(artist_choice, {})
                .get(song_choice)
            ):
                return await itr.followup.send("Song not found.")

            int_song_id = int(song[song_id_index])
            world_record, last_updated = await cog.get_world_record(
                game_choice.value, season_code, int_song_id
            )
            results = await cog.get_attributes(
                game_choice.value, "MusicData", [int_song_id], {"album": True}
            )

            msg = await itr.followup.send(
                embed=SongWorldRecordEmbed(
                    game_choice.value,
                    artist_choice,
                    song_choice,
                    season_code,
                    world_record,
                    last_updated,
                    results[int_song_id]["album"],
                    icon,
                ),
                files=(
                    [discord.File(icon, filename="icon.png")]
                    if isinstance(icon, Path)
                    else []
                ),
                wait=True,
            )
            view = SongWorldRecordView(
                msg,
                game_choice.value,
                artist_choice,
                song_choice,
                season_code,
                world_record,
                last_updated,
                itr.user,
                results[int_song_id]["album"],
                icon,
            )
            await msg.edit(view=view)
            return

        tasks = [
            cog.get_world_record(
                game_choice.value, season_code, int(song[song_id_index]), True
            )
            for song in songs
        ]
        results = await asyncio.gather(*tasks)
        world_records = {
            song: (
                "Error"
                if isinstance(result, Exception)
                else "None" if not result[0] else result[0][0]
            )
            for song, result in zip(
                self.bot.info_by_name[game_choice.value][artist_choice], results
            )
        }
        last_updated = max(
            (
                result[1]
                for result in results
                if not isinstance(result, Exception) and result[1]
            ),
            default=None,
        )

        msg = await itr.followup.send(
            embed=ArtistWorldRecordEmbed(
                game_choice.value,
                artist_choice,
                season_code,
                world_records,
                last_updated,
                icon,
            ),
            files=(
                [discord.File(icon, filename="icon.png")]
                if isinstance(icon, Path)
                else []
            ),
            wait=True,
        )
        view = ArtistWorldRecordView(
            msg,
            game_choice.value,
            artist_choice,
            season_code,
            world_records,
            last_updated,
            itr.user,
            icon,
        )
        await msg.edit(view=view)


async def setup(bot: "dBot") -> None:
    await bot.add_cog(WorldRecord(bot))
