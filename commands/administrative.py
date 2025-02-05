from discord.ext import commands

from static.dConsts import STATUS_CHANNEL


class Administrative(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def sync(self, ctx: commands.Context):
        if ctx.message.channel.id == STATUS_CHANNEL:
            msg = await ctx.send("Syncing...")
            await self.bot.tree.sync()
            self.bot.tree.clear_commands(guild=ctx.guild)
            await self.bot.tree.sync(guild=ctx.guild)
            await msg.edit(content="Synced!")

    @commands.command()
    @commands.is_owner()
    async def reload(self, ctx: commands.Context):
        if ctx.message.channel.id == STATUS_CHANNEL:
            msg = await ctx.send("Reloading...")
            await self.bot.reload_extension("app_commands.bonus")
            await self.bot.reload_extension("app_commands.ssLeague")
            await self.bot.reload_extension("tasks.notify_p9")
            await msg.edit(content="Extensions reloaded!")


async def setup(bot: commands.Bot):
    await bot.add_cog(Administrative(bot))
