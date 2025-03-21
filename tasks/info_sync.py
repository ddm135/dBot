import logging
from datetime import time
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

from static.dConsts import GAMES, TIMEZONES
from static.dHelpers import get_sheet_data

if TYPE_CHECKING:
    from dBot import dBot


class InfoSync(commands.Cog):
    ROLE_LOGGER = logging.getLogger(__name__)

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.info_sync.start()
        await super().cog_load()

    async def cog_unload(self) -> None:
        self.info_sync.cancel()
        self.bot.info.clear()
        await super().cog_unload()

    @tasks.loop(time=time(hour=12, tzinfo=TIMEZONES["KST"]))
    async def info_sync(self) -> None:
        self.bot.info_ready = False
        self.ROLE_LOGGER.info("Downloading song data...")
        await self.bot.wait_until_ready()
        await self.bot.unload_extension("tasks.clock")
        await self.bot.change_presence(
            status=discord.Status.dnd,
            activity=discord.CustomActivity("Downloading song data..."),
        )
        self.bot.info.clear()
        for game, game_details in GAMES.items():
            if not game_details["pinChannelIds"]:
                continue

            info = get_sheet_data(
                game_details["infoId"],
                game_details["infoSongs"],
            )
            for row in info:
                self.bot.info[game][
                    row[game_details["infoColumns"].index("artist_name")]
                ].append(row)
        await self.bot.load_extension("tasks.clock")
        self.bot.info_ready = True

    @info_sync.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()
        await self.info_sync()


async def setup(bot: "dBot") -> None:
    await bot.add_cog(InfoSync(bot))
