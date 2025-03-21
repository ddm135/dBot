from datetime import time
from typing import TYPE_CHECKING

from discord.ext import commands, tasks

from static.dConsts import GAMES, TIMEZONES
from static.dHelpers import get_sheet_data

if TYPE_CHECKING:
    from dBot import dBot


class InfoSync(commands.Cog):
    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await self.info_sync()
        self.info_sync.start()
        await super().cog_load()

    async def cog_unload(self) -> None:
        self.info_sync.cancel()
        await super().cog_unload()

    @tasks.loop(time=time(hour=12, tzinfo=TIMEZONES["KST"]))
    async def info_sync(self) -> None:
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

    @info_sync.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: "dBot") -> None:
    await bot.add_cog(InfoSync(bot))
