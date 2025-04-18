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

STEP = 10


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
    @app_commands.rename(game_choice="game", artist_name="artist/album")
    async def info(
        self,
        itr: discord.Interaction["dBot"],
        game_choice: app_commands.Choice[str],
        artist_name: str | None = None,
    ) -> None:
        """View song information.

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
        duration_column = game_details["infoColumns"].index("duration")

        if not artist_name:
            _songs = self.bot.info_by_id[game_choice.value].values()
        else:
            if artist_name not in self.bot.info_by_name[game_choice.value]:
                return await itr.followup.send("Artist not found.")

            _songs = self.bot.info_by_name[game_choice.value][artist_name].values()

        songs = sorted(_songs, key=lambda x: x[duration_column])
        msg = await itr.followup.send(
            embed=create_embed(game_details, artist_name, songs), wait=True
        )
        view = InfoView(msg, game_details, artist_name, songs)
        await msg.edit(view=view)


class InfoView(discord.ui.View):
    current = 1
    max = 1

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
        self.max = math.ceil(len(songs) / STEP)
        super().__init__(timeout=60)

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await self.message.edit(view=self)

    async def update_message(self) -> None:
        await self.message.edit(
            embed=create_embed(
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


def create_embed(
    game_details: "GameDetails",
    artist: str | None,
    songs: list[list[str]],
    current: int = 1,
    max: int | None = None,
) -> discord.Embed:
    end = current * STEP
    start = end - STEP
    filtered_songs = songs[start:end]
    duration_index = game_details["infoColumns"].index("duration")
    artist_name_index = game_details["infoColumns"].index("artist_name")
    song_name_index = game_details["infoColumns"].index("song_name")

    description = "\n".join(
        f"({(f"{song[duration_index]}" if ":" in song[duration_index] else
             f"{int(song[duration_index]) // 60}:"
             f"{int(song[duration_index]) % 60:02d}")}) "
        f"{(f"{song[artist_name_index].replace(r"*", r"\*").replace(r"_", r"\_")} - "
            if not artist else "")}"
        f"**{song[song_name_index].replace(r"*", r"\*").replace(r"_", r"\_")}**"
        for song in filtered_songs
    )
    embed = discord.Embed(
        title=f"{game_details["name"]}{f" - {artist}" if artist else ""}",
        description=description,
        color=game_details["color"],
    )
    embed.set_footer(text=f"Page {current}/{max or math.ceil(len(songs) / STEP)}")
    return embed


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Info(bot))
