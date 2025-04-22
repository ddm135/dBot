import math
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from app_commands.autocomplete.info import artist_autocomplete
from statics.consts import GAMES

if TYPE_CHECKING:
    from dBot import dBot
    from statics.types import GameDetails


class Info(commands.Cog):
    STEP = 10
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
            embed=self.create_embed(game_details, artist_name, sorted_songs), wait=True
        )
        view = self.InfoView(msg, game_details, artist_name, sorted_songs)
        await msg.edit(view=view)

    class InfoView(discord.ui.View):

        def __init__(
            self,
            message: discord.Message,
            game_details: "GameDetails",
            artist: str | None,
            songs: list[list[str]],
        ) -> None:
            self.message = message
            self.game_details = game_details
            self.artist = artist
            self.songs = songs
            self.current = 1
            self.max = math.ceil(len(songs) / Info.STEP) or 1
            super().__init__(timeout=60)

        async def on_timeout(self) -> None:
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
            await self.message.edit(view=self)

        async def update_message(self) -> None:
            await self.message.edit(
                embed=Info.create_embed(
                    self.game_details, self.artist, self.songs, self.current, self.max
                ),
                view=self,
            )

        @discord.ui.button(label="Previous Page", style=discord.ButtonStyle.secondary)
        async def previous_page(
            self, itr: discord.Interaction["dBot"], button: discord.ui.Button
        ) -> None:
            await itr.response.defer()
            self.current -= 1
            if self.current < 1:
                self.current = self.max
            await self.update_message()

        @discord.ui.button(label="Next Page", style=discord.ButtonStyle.primary)
        async def next_page(
            self, itr: discord.Interaction["dBot"], button: discord.ui.Button
        ) -> None:
            await itr.response.defer()
            self.current += 1
            if self.current > self.max:
                self.current = 1
            await self.update_message()

    @classmethod
    def create_embed(
        cls,
        game_details: "GameDetails",
        artist: str | None,
        songs: list[list[str]],
        current: int = 1,
        max: int | None = None,
    ) -> discord.Embed:
        end = current * cls.STEP
        start = end - cls.STEP
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
        embed = discord.Embed(
            title=f"{game_details["name"]}{f" - {artist}" if artist else ""}",
            description=description,
            color=game_details["color"],
        )
        embed.set_footer(
            text=f"Page {current}/{max or math.ceil(len(songs) / Info.STEP)}"
        )
        return embed


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Info(bot))
