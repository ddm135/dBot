from typing import TYPE_CHECKING

import discord
from asteval import Interpreter  # type: ignore[import-untyped]
from discord.ext import commands

from statics.consts import EXTENSIONS, STATUS_CHANNEL

if TYPE_CHECKING:
    from dBot import dBot


class Administrative(commands.Cog):

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot
        self.eval = Interpreter(
            minimal=True,
            symtable={"bot": bot},
            builtins_readonly=True,
            config={"listcomp": True},
        )

    @commands.command()
    @commands.is_owner()
    async def sync(self, ctx: commands.Context) -> None:
        if ctx.channel.id != STATUS_CHANNEL:
            return

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
    async def load(self, ctx: commands.Context, *extensions: str) -> None:
        if ctx.channel.id != STATUS_CHANNEL:
            return

        msg = await ctx.send("Loading extensions...")

        if not extensions:
            extensions = EXTENSIONS
        else:
            for ext in extensions:
                if ext not in EXTENSIONS:
                    await msg.edit(content=f"Invalid extension: {ext}")
                    return

        for ext in extensions:
            await self.bot.load_extension(ext)
            if ext == "tasks.clock":
                await self.bot.change_presence(
                    status=discord.Status.dnd,
                    activity=discord.CustomActivity("Waiting for clock..."),
                )
        await msg.edit(content="Loaded!")

    @commands.command()
    @commands.is_owner()
    async def unload(self, ctx: commands.Context, *extensions: str) -> None:
        if ctx.channel.id != STATUS_CHANNEL:
            return

        msg = await ctx.send("Unloading extensions...")

        if not extensions:
            extensions = EXTENSIONS
        else:
            for ext in extensions:
                if ext not in EXTENSIONS:
                    await msg.edit(content=f"Invalid extension: {ext}")
                    return

        for ext in extensions:
            await self.bot.unload_extension(ext)
            if ext == "tasks.clock":
                await self.bot.change_presence(
                    status=discord.Status.dnd,
                    activity=discord.CustomActivity("Clock is disabled."),
                )
        await msg.edit(content="Unloaded!")

    @commands.command()
    @commands.is_owner()
    async def reload(self, ctx: commands.Context, *extensions: str) -> None:
        if ctx.channel.id != STATUS_CHANNEL:
            return

        msg = await ctx.send("Reloading extensions...")

        if not extensions:
            extensions = EXTENSIONS
        else:
            for ext in extensions:
                if ext not in EXTENSIONS:
                    await msg.edit(content=f"Invalid extension: {ext}")
                    return

        for ext in extensions:
            await self.bot.reload_extension(ext)
            if ext == "tasks.clock":
                await self.bot.change_presence(
                    status=discord.Status.dnd,
                    activity=discord.CustomActivity("Waiting for clock..."),
                )
        await msg.edit(content="Reloaded!")

    @commands.command()
    @commands.is_owner()
    async def echo(self, ctx: commands.Context, *, message: str) -> None:
        if ctx.channel.id != STATUS_CHANNEL:
            return

        await ctx.send(message)

    @commands.command()
    @commands.is_owner()
    async def print(self, ctx: commands.Context, *, message: str) -> None:
        if ctx.channel.id != STATUS_CHANNEL:
            return

        print(self.eval(message))

    async def cog_command_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.errors.NotOwner):
            return
        raise error


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Administrative(bot))
