from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from static.dConsts import TIMEZONES


class Clock(commands.Cog):
    STEP = 2
    TIMEZONE_ITEMS = list(TIMEZONES.items())
    TIMEZONE_COUNT = len(TIMEZONES)

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.counter = 0
        self.clock.start()

    async def cog_unload(self):
        self.clock.cancel()

    @tasks.loop(seconds=10)
    async def clock(self):
        short_name1, timezone1 = self.TIMEZONE_ITEMS[self.counter]
        short_name2, timezone2 = self.TIMEZONE_ITEMS[self.counter + 1]
        current_time1 = self._format_current_time(timezone1, short_name1)
        current_time2 = self._format_current_time(timezone2, short_name2)

        await self.bot.change_presence(
            activity=discord.Game(name=f"{current_time1}; {current_time2}")
        )
        self.counter = (self.counter + self.STEP) % self.TIMEZONE_COUNT

    @clock.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

    @staticmethod
    def _format_current_time(timezone: str, short_name: str) -> str:
        return datetime.now(ZoneInfo(timezone)).strftime(f"%H:%M {short_name}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Clock(bot))
