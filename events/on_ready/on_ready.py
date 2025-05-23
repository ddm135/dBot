from datetime import datetime
from typing import TYPE_CHECKING

from discord.ext import commands

from statics.consts import STATUS_CHANNEL

if TYPE_CHECKING:
    from dBot import dBot


class OnReady(commands.Cog):
    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    @commands.Cog.listener("on_ready")
    async def on_ready(self) -> None:
        await self.bot.get_channel(STATUS_CHANNEL).send(  # type: ignore[union-attr]
            f"Successful start at {datetime.now()}"
        )


async def setup(bot: "dBot") -> None:
    await bot.add_cog(OnReady(bot))
