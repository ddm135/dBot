from datetime import datetime
from zoneinfo import ZoneInfo

from discord.ext import commands


class Memes(commands.Cog):
    MOTS7_RELEASE = datetime(year=2020, month=2, day=21, tzinfo=ZoneInfo("Asia/Seoul"))
    LP_RELEASE = datetime(year=2020, month=11, day=30, tzinfo=ZoneInfo("Asia/Seoul"))

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def mots7(self, ctx: commands.Context):
        diff = self._days_since_release(self.MOTS7_RELEASE)
        await ctx.send(f"It has been {diff} days since Map of The Soul: 7 release.")

    @commands.command()
    async def got7(self, ctx: commands.Context):
        diff = self._days_since_release(self.LP_RELEASE)
        await ctx.send(f"It has been {diff} days since Last Piece release.")

    @staticmethod
    def _days_since_release(release_date: datetime):
        current = datetime.now(tz=ZoneInfo("Asia/Seoul"))
        diff = current - release_date
        return diff.days


async def setup(bot: commands.Bot):
    await bot.add_cog(Memes(bot))
