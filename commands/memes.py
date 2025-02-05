from datetime import datetime
from zoneinfo import ZoneInfo

from discord.ext import commands


class Memes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def mots7(self, ctx: commands.Context):
        mots7_release = datetime(
            year=2020, month=2, day=21, tzinfo=ZoneInfo("Asia/Seoul")
        )
        current = datetime.now(tz=ZoneInfo("Asia/Seoul"))
        diff = current - mots7_release
        await ctx.send(f"It has been {diff.days} days since MOTS:7 release.")

    @commands.command()
    async def got7(self, ctx: commands.Context):
        mots7_release = datetime(
            year=2020, month=11, day=30, tzinfo=ZoneInfo("Asia/Seoul")
        )
        current = datetime.now(tz=ZoneInfo("Asia/Seoul"))
        diff = current - mots7_release
        await ctx.send(f"It has been {diff.days} days since Last Piece release.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Memes(bot))
