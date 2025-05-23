import importlib
import sys
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from statics.consts import GAMES

if (AUTOCOMPLETES := "app_commands.autocompletes.info") in sys.modules:
    importlib.reload(sys.modules[AUTOCOMPLETES])
from app_commands.autocompletes.info import artist_autocomplete

if (COMMONS := "app_commands.commons.info") in sys.modules:
    importlib.reload(sys.modules[COMMONS])

if (EMBEDS := "app_commands.embeds.info") in sys.modules:
    importlib.reload(sys.modules[EMBEDS])
from app_commands.embeds.info import InfoEmbed

if (VIEWS := "app_commands.views.info") in sys.modules:
    importlib.reload(sys.modules[VIEWS])
from app_commands.views.info import InfoView

if TYPE_CHECKING:
    from dBot import dBot


class Info(commands.Cog):
    GAME_CHOICES = [
        app_commands.Choice(name=game["name"], value=key)
        for key, game in GAMES.items()
        if game["infoId"]
    ]

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    @app_commands.command()
    @app_commands.choices(game_choice=GAME_CHOICES)
    @app_commands.autocomplete(artist_name=artist_autocomplete)
    @app_commands.rename(game_choice="game", artist_name="artist")
    async def info(
        self,
        itr: discord.Interaction["dBot"],
        game_choice: app_commands.Choice[str],
        artist_name: str | None = None,
    ) -> None:
        """View song information, sorted by duration

        Parameters
        -----------
        game_choice: Choice[:class:`str`]
            Game
        artist_name: Optional[:class:`str`]
            Artist Name
        """

        await itr.response.defer()
        if not self.bot.info_data_ready:
            return await itr.followup.send(
                "Song data synchronization in progress, feature unavailable."
            )

        game_details = GAMES[game_choice.value]
        duration_index = game_details["infoColumns"].index("duration")

        if not artist_name:
            songs = self.bot.info_by_id[game_choice.value].values()
        else:
            if artist_name not in self.bot.info_by_name[game_choice.value]:
                return await itr.followup.send("Artist not found.")

            songs = self.bot.info_by_name[game_choice.value][artist_name].values()

        sorted_songs = sorted(songs, key=lambda x: x[duration_index])
        msg = await itr.followup.send(
            embed=InfoEmbed(game_details, artist_name, sorted_songs),
            wait=True,
        )
        view = InfoView(msg, game_details, artist_name, sorted_songs, itr.user)
        await msg.edit(view=view)


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Info(bot))
