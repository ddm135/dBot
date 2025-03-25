from datetime import datetime
from typing import TYPE_CHECKING

from discord.ext import commands

from statics.consts import TIMEZONES

if TYPE_CHECKING:
    from dBot import dBot


class Memes(commands.Cog):
    MOTS7_RELEASE = datetime(year=2020, month=2, day=21, tzinfo=TIMEZONES["KST"])
    LP_RELEASE = datetime(year=2020, month=11, day=30, tzinfo=TIMEZONES["KST"])
    BAEMON_DEBUT = datetime(year=2024, month=4, day=1, tzinfo=TIMEZONES["KST"])
    BONUSBOT_DEATH = datetime(
        year=2025, month=3, day=24, hour=4, minute=35, tzinfo=TIMEZONES["KST"]
    )

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def mots7(self, ctx: commands.Context) -> None:
        diff = self.days_since(self.MOTS7_RELEASE)
        await ctx.send(f"It has been {diff} days since Map of The Soul: 7's release.")

    @commands.command()
    @commands.is_owner()
    async def got7(self, ctx: commands.Context) -> None:
        diff = self.days_since(self.LP_RELEASE)
        await ctx.send(f"It has been {diff} days since Last Piece's release.")

    @commands.command()
    @commands.is_owner()
    async def baemon(self, ctx: commands.Context) -> None:
        diff = self.days_since(self.BAEMON_DEBUT)
        await ctx.send(f"It has been {diff} days since BABYMONSTER's official debut.")

    @commands.command()
    @commands.is_owner()
    async def bonusbot(self, ctx: commands.Context) -> None:
        diff = self.days_since(self.BONUSBOT_DEATH)
        await ctx.send(f"It has been {diff} days since bonusBot's death.")

    def days_since(self, date: datetime) -> int:
        current = datetime.now(tz=date.tzinfo)
        diff = current - date
        return diff.days


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Memes(bot))
