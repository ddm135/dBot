import discord
from discord.ext import commands

from dBot import dBot
from static.dConsts import EXTENSIONS, STATUS_CHANNEL


class Administrative(commands.Cog):
    def __init__(self, bot: dBot) -> None:
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def sync(self, ctx: commands.Context) -> None:
        if ctx.channel.id == STATUS_CHANNEL:
            msg = await ctx.send("Syncing app commands...")
            try:
                await self.bot.tree.sync()
                self.bot.tree.clear_commands(guild=ctx.guild)
                await self.bot.tree.sync(guild=ctx.guild)
                await msg.edit(content="Synced!")
            except discord.RateLimited as e:
                await msg.edit(content="Rate limited.")
                print(e)

    @commands.command()
    @commands.is_owner()
    async def reload(self, ctx: commands.Context) -> None:
        if ctx.channel.id == STATUS_CHANNEL:
            msg = await ctx.send("Reloading extensions...")
            await self.bot.change_presence(
                status=discord.Status.dnd,
                activity=discord.Game(name="Reloading extensions..."),
            )
            for ext in EXTENSIONS:
                await self.bot.reload_extension(ext)
            await msg.edit(content="Reloaded!")


async def setup(bot: dBot) -> None:
    await bot.add_cog(Administrative(bot))
