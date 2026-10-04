"""Small day counters."""

from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from discord.ext import commands

if TYPE_CHECKING:
    from bot import dBot

type Ctx = commands.Context[dBot]

KST = ZoneInfo("Asia/Seoul")

MOTS7_RELEASE = datetime(2020, 2, 21, tzinfo=KST)
LP_RELEASE = datetime(2020, 11, 30, tzinfo=KST)
BAEMON_DEBUT = datetime(2024, 4, 1, tzinfo=KST)
BONUSBOT_DEATH = datetime(2025, 3, 24, 6, 35, tzinfo=KST)


def days_since(moment: datetime, now: datetime | None = None) -> int:
    now = now or datetime.now(tz=moment.tzinfo)
    return (now - moment).days


class Miscellaneous(commands.Cog):
    def __init__(self, bot: dBot) -> None:
        self.bot = bot

    @commands.command()
    async def mots7(self, ctx: Ctx) -> None:
        days = days_since(MOTS7_RELEASE)
        await ctx.send(f"It has been {days} days since Map of The Soul: 7's release.")

    @commands.command()
    async def got7(self, ctx: Ctx) -> None:
        days = days_since(LP_RELEASE)
        await ctx.send(f"It has been {days} days since Last Piece's release.")

    @commands.command()
    async def baemon(self, ctx: Ctx) -> None:
        days = days_since(BAEMON_DEBUT)
        await ctx.send(f"It has been {days} days since BABYMONSTER's official debut.")

    @commands.command()
    async def bonusbot(self, ctx: Ctx) -> None:
        days = days_since(BONUSBOT_DEATH)
        await ctx.send(f"It has been {days} days since bonusBot's death.")


async def setup(bot: dBot) -> None:
    await bot.add_cog(Miscellaneous(bot))
