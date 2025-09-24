from datetime import datetime
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from statics.consts import STATUS_CHANNEL

if TYPE_CHECKING:
    from dBot import dBot


class OnReady(commands.Cog):
    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    @commands.Cog.listener("on_ready")
    async def on_ready(self) -> None:
        channel = self.bot.get_channel(STATUS_CHANNEL) or await self.bot.fetch_channel(
            STATUS_CHANNEL
        )
        assert isinstance(channel, discord.TextChannel)
        await channel.send(f"Successful start at {datetime.now()}")


async def setup(bot: "dBot") -> None:
    await bot.add_cog(OnReady(bot))
