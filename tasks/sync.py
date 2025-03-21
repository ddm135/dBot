from datetime import time

from discord.ext import commands, tasks

from dBot import dBot
from static.dConsts import GAMES, TIMEZONES
from static.dHelpers import get_sheet_data


class Sync(commands.Cog):
    def __init__(self, bot: dBot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.sync.start()
        await super().cog_load()

    async def cog_unload(self) -> None:
        self.sync.cancel()
        await super().cog_unload()

    @tasks.loop(time=time(hour=12, tzinfo=TIMEZONES["KST"]))
    async def sync(self) -> None:
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

    @sync.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: dBot) -> None:
    await bot.add_cog(Sync(bot))
