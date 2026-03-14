from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from dBot import dBot


class Alice(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot


async def setup(bot: "dBot"):
    await bot.add_cog(Alice(bot))
