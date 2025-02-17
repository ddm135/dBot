from datetime import datetime

from discord.ext import commands

from static.dConsts import TIMEZONES


class Memes(commands.Cog):
    MOTS7_RELEASE = datetime(year=2020, month=2, day=21, tzinfo=TIMEZONES["KST"])
    LP_RELEASE = datetime(year=2020, month=11, day=30, tzinfo=TIMEZONES["KST"])
    BAEMON_DEBUT = datetime(year=2024, month=4, day=1, tzinfo=TIMEZONES["KST"])

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command()
    async def mots7(self, ctx: commands.Context) -> None:
        diff = self._days_since(self.MOTS7_RELEASE)
        await ctx.send(f"It has been {diff} days since Map of The Soul: 7 release.")

    @commands.command()
    async def got7(self, ctx: commands.Context) -> None:
        diff = self._days_since(self.LP_RELEASE)
        await ctx.send(f"It has been {diff} days since Last Piece release.")

    @commands.command()
    async def baemon(self, ctx: commands.Context) -> None:
        diff = self._days_since(self.BAEMON_DEBUT)
        await ctx.send(f"It has been {diff} days since BABYMONSTER official debut.")

    def _days_since(self, date: datetime) -> int:
        current = datetime.now(tz=date.tzinfo)
        diff = current - date
        return diff.days


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Memes(bot))
