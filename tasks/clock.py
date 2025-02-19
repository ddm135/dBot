from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from static.dConsts import TIMEZONES


class Clock(commands.Cog):
    STEP = 2
    TIMEZONE_ITEMS = list(TIMEZONES.items())
    TIMEZONE_COUNT = len(TIMEZONES)

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.counter = 0

    async def cog_load(self) -> None:
        self.clock.start()
        await super().cog_load()

    async def cog_unload(self) -> None:
        self.clock.cancel()
        await super().cog_unload()

    @tasks.loop(seconds=10)
    async def clock(self) -> None:
        short_name1, timezone1 = self.TIMEZONE_ITEMS[self.counter]
        short_name2, timezone2 = self.TIMEZONE_ITEMS[self.counter + 1]
        current_time1 = self._format_current_time(timezone1, short_name1)
        current_time2 = self._format_current_time(timezone2, short_name2)

        await self.bot.change_presence(
            activity=discord.Game(name=f"{current_time1}; {current_time2}")
        )
        self.counter = (self.counter + self.STEP) % self.TIMEZONE_COUNT

    @clock.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()

    def _format_current_time(self, timezone: ZoneInfo, short_name: str) -> str:
        return datetime.now(timezone).strftime(f"%H:%M {short_name}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Clock(bot))
