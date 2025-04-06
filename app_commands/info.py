import math
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

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

    async def info(
        self,
        itr: discord.Interaction["dBot"],
        game_choice: app_commands.Choice[str],
        artist_name: str | None = None,
    ) -> None:
        pass

        await itr.response.defer()
        if not self.bot.info_data_ready:
            return await itr.followup.send(
                "Song data synchronization in progress, feature unavailable.",
                ephemeral=True,
            )

        game_details = GAMES[game_choice.value]
        duration_column = game_details["infoColumns"].index("duration")

        if not artist_name:
            _songs = self.bot.info_by_id[game_choice.value].values()
        else:
            _songs = self.bot.info_by_name[game_choice.value][artist_name].values()
        songs = sorted(_songs, key=lambda x: int(x[duration_column]))
        msg = await itr.followup.send(
            embed=create_embed(game_details, artist_name, songs), wait=True
        )
        view = InfoView(msg, game_details, artist_name, songs)
        await msg.edit(view=view)


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
    song_name_index = game_details["infoColumns"].index("song_name")
    description = "\n".join(
        f"({int(song[duration_index]) // 60}:{int(song[duration_index]) % 60:02d}) **"
        f"{song[song_name_index].replace(r"*", r"\*").replace(r"_", r"\_")}**"
        for song in filtered_songs
    )
    embed = discord.Embed(
        title=f"{game_details["name"]}{f" - {artist}" if artist else ""}",
        description=description,
        color=game_details["color"],
    )
    embed.set_footer(text=f"Page {current} of {max or math.ceil(len(songs) / STEP)}")
    return embed


class InfoView(discord.ui.View):
    current = 1
    max = 1

    def __init__(
        self,
        message: discord.Message,
        game_details: "GameDetails",
        artist: str | None,
        songs: list[list[str]],
    ):
        self.message = message
        self.game_details = game_details
        self.artist = artist
        self.songs = songs
        self.max = math.ceil(len(songs) / STEP)
        super().__init__(timeout=60)

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
        self.current -= 1
        if self.current < 1:
            self.current = self.max
        await self.update_message()

    @discord.ui.button(label="Next Page", style=discord.ButtonStyle.primary)
    async def next_page(
        self, itr: discord.Interaction["dBot"], button: discord.ui.Button
    ) -> None:
        self.current += 1
        if self.current > self.max:
            self.current = 1
        await self.update_message()


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Info(bot))
