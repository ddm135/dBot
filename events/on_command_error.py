from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from dBot import dBot


class OnCommandError(commands.Cog):
    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    @commands.Cog.listener("on_command_error")
    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.errors.NotOwner):
            return
        raise error


async def setup(bot: "dBot") -> None:
    await bot.add_cog(OnCommandError(bot))
