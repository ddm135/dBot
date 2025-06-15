from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from statics.consts import ME, STATUS_CHANNEL

if TYPE_CHECKING:
    from dBot import dBot


class OnCommandError(commands.Cog):
    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    @commands.Cog.listener("on_command_error")
    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(
            error,
            (
                commands.NotOwner,
                commands.CommandNotFound,
                commands.MissingRequiredArgument,
            ),
        ):
            return

        channel = self.bot.get_channel(STATUS_CHANNEL) or await self.bot.fetch_channel(
            STATUS_CHANNEL
        )
        assert isinstance(channel, discord.TextChannel)
        await channel.send(f"<@{ME}> Something happened.")

        raise error


async def setup(bot: "dBot") -> None:
    await bot.add_cog(OnCommandError(bot))
