from datetime import datetime, time
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from static.dConsts import TIMEZONES


class Clock(commands.Cog):
    STEP = 1
    TIMEZONE_ITEMS = list(TIMEZONES.items())
    TIMEZONE_COUNT = len(TIMEZONES)
    counter = 0

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.clock.start()
        await super().cog_load()

    async def cog_unload(self) -> None:
        self.clock.cancel()
        await super().cog_unload()

    @tasks.loop(time=[
        time(hour=h, minute=m, second=s)
        for h in range(24)
        for m in range(60)
        for s in range(0, 60, 10)
    ])
    async def clock(self) -> None:
        short_name, timezone = self.TIMEZONE_ITEMS[self.counter]
        current_time = self._format_current_time(timezone, short_name)

        await self.bot.change_presence(
            activity=discord.Game(name=f"{current_time}")
        )
        self.counter = (self.counter + self.STEP) % self.TIMEZONE_COUNT

    @clock.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()

    def _format_current_time(self, timezone: ZoneInfo, short_name: str) -> str:
        return datetime.now(timezone).strftime(f"%H:%M {short_name} %b %d")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Clock(bot))
