from datetime import datetime, time
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

from statics.consts import TIMEZONES

if TYPE_CHECKING:
    from dBot import dBot


class Clock(commands.Cog):
    STEP = 1
    TIMEZONE_ITEMS = tuple(TIMEZONES.items())
    TIMEZONE_COUNT = len(TIMEZONES)

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot
        self.counter = 0

    async def cog_load(self) -> None:
        self.clock.start()

    async def cog_unload(self) -> None:
        self.clock.cancel()

    @tasks.loop(time=[time(hour=h, minute=m) for h in range(24) for m in range(60)])
    async def clock(self) -> None:
        short_name, timezone = self.TIMEZONE_ITEMS[self.counter]
        current_time = (
            datetime.now(tz=timezone)
            .strftime(f"%B %d %Y, %H:%M {short_name}")
            .replace(" 0", " ")
        )

        await self.bot.change_presence(
            activity=discord.CustomActivity(f"{current_time}")
        )
        self.counter = (self.counter + self.STEP) % self.TIMEZONE_COUNT

    @clock.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Clock(bot))
