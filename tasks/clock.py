from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from static.dConsts import TIMEZONES


class Clock(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.counter = 0
        self.clock.start()

    async def cog_unload(self):
        self.clock.cancel()

    @tasks.loop(seconds=10)
    async def clock(self):
        sn1, zinf1 = list(TIMEZONES.items())[self.counter]
        sn2, zinf2 = list(TIMEZONES.items())[self.counter + 1]
        current1 = datetime.now(ZoneInfo(zinf1)).strftime(f"%H:%M {sn1}")
        current2 = datetime.now(ZoneInfo(zinf2)).strftime(f"%H:%M {sn2}")

        await self.bot.change_presence(
            activity=discord.Game(name=f"{current1}; {current2}")
        )
        self.counter = (self.counter + 2) % 4

    @clock.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Clock(bot))
