from datetime import datetime, time
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

from static.dConsts import TIMEZONES

if TYPE_CHECKING:
    from dBot import dBot


class Clock(commands.Cog):
    STEP = 1
    TIMEZONE_ITEMS = list(TIMEZONES.items())
    TIMEZONE_COUNT = len(TIMEZONES)
    counter = 0

    def __init__(self, bot: dBot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.clock.start()
        await super().cog_load()

    async def cog_unload(self) -> None:
        self.clock.cancel()
        await super().cog_unload()

    @tasks.loop(time=[time(hour=h, minute=m) for h in range(24) for m in range(60)])
    async def clock(self) -> None:
        short_name, timezone = self.TIMEZONE_ITEMS[self.counter]
        current_time = datetime.now(timezone).strftime(f"%H:%M {short_name} %b %d")

        await self.bot.change_presence(
            status=self.bot.status, activity=discord.Game(name=f"{current_time}")
        )
        self.counter = (self.counter + self.STEP) % self.TIMEZONE_COUNT

    @clock.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: dBot) -> None:
    await bot.add_cog(Clock(bot))
