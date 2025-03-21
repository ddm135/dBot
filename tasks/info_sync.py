import asyncio
import logging
from datetime import time
from typing import TYPE_CHECKING

from discord.ext import commands, tasks

from static.dConsts import GAMES, TIMEZONES
from static.dHelpers import get_sheet_data

if TYPE_CHECKING:
    from dBot import dBot


class InfoSync(commands.Cog):
    LOGGER = logging.getLogger(__name__)

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await self.info_sync()
        self.info_sync.start()
        self.bot.info_data_ready = True
        await super().cog_load()

    async def cog_unload(self) -> None:
        self.bot.info_data_ready = False
        self.info_sync.cancel()
        self.bot.info_by_name.clear()
        await super().cog_unload()

    @tasks.loop(time=time(hour=12, tzinfo=TIMEZONES["KST"]))
    async def info_sync(self) -> None:
        self.LOGGER.info("Downloading song data...")
        self.bot.info_by_name.clear()
        for game, game_details in GAMES.items():
            if not game_details["pinChannelIds"]:
                continue

            info = get_sheet_data(
                game_details["infoId"],
                game_details["infoSongs"],
            )
            for row in info:
                self.bot.info_by_name[game][
                    row[game_details["infoColumns"].index("artist_name")]
                ].append(row)
                self.bot.info_by_id[game][
                    row[game_details["infoColumns"].index("song_id")]
                ] = row

    @info_sync.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()
        self.bot.info_data_ready = False
        await asyncio.sleep(5)

    @info_sync.after_loop
    async def after_loop(self) -> None:
        if not self.info_sync.is_being_cancelled():
            await asyncio.sleep(5)
            self.bot.info_data_ready = True


async def setup(bot: "dBot") -> None:
    await bot.add_cog(InfoSync(bot))
