# pyright: reportTypedDictNotRequiredAccess=false

from pathlib import Path
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from statics.consts import GAMES

from .autocompletes import artist_autocomplete
from .embeds import InfoEmbed
from .views import InfoView

if TYPE_CHECKING:
    from dBot import dBot


class Info(commands.Cog):
    GAME_CHOICES = [
        app_commands.Choice(name=game_details["name"], value=game)
        for game, game_details in GAMES.items()
        if {"info"} <= set(game_details)
    ]

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    @app_commands.command()
    @app_commands.choices(game_choice=GAME_CHOICES)
    @app_commands.autocomplete(artist_choice=artist_autocomplete)
    @app_commands.rename(game_choice="game", artist_choice="artist")
    async def info(
        self,
        itr: discord.Interaction["dBot"],
        game_choice: app_commands.Choice[str],
        artist_choice: str | None = None,
    ) -> None:
        """View song information, sorted by duration

        Parameters
        -----------
        game_choice: Choice[:class:`str`]
            Game
        artist_choice: Optional[:class:`str`]
            Artist Name
        """

        await itr.response.defer()
        game_details = GAMES[game_choice.value]
        song_id_index = game_details["info"]["columns"].index("song_id")

        icon: str | Path | None
        if not artist_choice:
            songs = self.bot.info_by_id[game_choice.value].values()
            icon = self.bot.basic[game_choice.value]["iconUrl"]
        else:
            if not (
                songs := (
                    self.bot.info_by_name[game_choice.value]
                    .get(artist_choice, {})
                    .values()
                )
            ):
                return await itr.followup.send("Artist not found.")
            icon = self.bot.emblem[game_choice.value][artist_choice]

        sorted_songs = sorted(
            songs,
            key=lambda x: self.bot.info_from_file[game_choice.value][x[song_id_index]][
                "sound"
            ]["duration"],
        )
        msg = await itr.followup.send(
            embed=InfoEmbed(
                game_choice.value,
                artist_choice,
                sorted_songs,
                self.bot.info_from_file[game_choice.value],
                icon,
            ),
            files=[discord.File(icon)] if isinstance(icon, Path) else [],
            wait=True,
        )
        view = InfoView(
            msg,
            game_choice.value,
            artist_choice,
            sorted_songs,
            self.bot.info_from_file[game_choice.value],
            itr.user,
            icon,
        )
        await msg.edit(view=view)


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Info(bot))
