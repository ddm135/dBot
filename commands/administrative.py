import discord
from discord.ext import commands

from static.dConsts import STATUS_CHANNEL


class Administrative(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def sync(self, ctx: commands.Context):
        if ctx.message.channel.id == STATUS_CHANNEL:
            msg = await ctx.send("Syncing app commands...")
            await self.bot.tree.sync()
            self.bot.tree.clear_commands(guild=ctx.guild)
            await self.bot.tree.sync(guild=ctx.guild)
            await msg.edit(content="Synced!")

    @commands.command()
    @commands.is_owner()
    async def reload(self, ctx: commands.Context):
        if ctx.message.channel.id == STATUS_CHANNEL:
            msg = await ctx.send("Reloading extensions...")
            await self.bot.change_presence(
                status=discord.Status.dnd,
                activity=discord.Game(name="Reloading extensions..."),
            )
            await self.bot.reload_extension("commands.administrative")
            await self.bot.reload_extension("commands.memes")
            await self.bot.reload_extension("app_commands.bonus")
            await self.bot.reload_extension("app_commands.ssLeague")
            await self.bot.reload_extension("tasks.clock")
            await self.bot.reload_extension("tasks.notify_p8")
            await self.bot.reload_extension("tasks.notify_p9")
            await msg.edit(content="Reloaded!")


async def setup(bot: commands.Bot):
    await bot.add_cog(Administrative(bot))
