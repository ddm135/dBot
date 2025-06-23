# mypy: disable-error-code="union-attr"
# pyright: reportAttributeAccessIssue=false, reportOptionalMemberAccess=false

import asyncio
import importlib
import logging
import sys
from pprint import pprint
from typing import TYPE_CHECKING, Annotated

import discord
from asteval import Interpreter  # type: ignore[import-untyped]
from discord.ext import commands

from statics.consts import (
    EXTENSIONS,
    GAMES,
    STATIC_MODULES,
    STATUS_CHANNEL,
    TIMEZONES,
)

if TYPE_CHECKING:
    from dBot import dBot


class Administrative(commands.Cog):
    LOGGER = logging.getLogger(__name__.rpartition(".")[0])

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
    async def pull(self, ctx: commands.Context) -> None:
        if ctx.channel.id != STATUS_CHANNEL:
            return

        msg = await ctx.send("Pulling changes...")
        process = await asyncio.create_subprocess_exec(
            "git",
            "pull",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        self.LOGGER.info(stdout.decode())
        if process.returncode:
            self.LOGGER.error(stderr.decode())
            await msg.edit(content="Error pulling changes.")
            return
        await msg.edit(content="Success!")

    @commands.command()
    @commands.is_owner()
    async def sync(self, ctx: commands.Context) -> None:
        if ctx.channel.id != STATUS_CHANNEL:
            return

        msg = await ctx.send("Syncing app commands...")
        try:
            await self.bot.tree.sync()
        except discord.RateLimited:
            await msg.edit(content="Rate limited.")
        else:
            await msg.edit(content="Synced!")

    @commands.command()
    @commands.is_owner()
    async def load(self, ctx: commands.Context, *extensions: str) -> None:
        if ctx.channel.id != STATUS_CHANNEL:
            return

        msg = await ctx.send("Loading extensions...")

        if not extensions:
            extensions = EXTENSIONS
            for module in STATIC_MODULES:
                importlib.reload(sys.modules[module])
        else:
            for ext in extensions:
                if ext not in EXTENSIONS:
                    await msg.edit(content=f"Invalid extension: {ext}")
                    return

        for ext in extensions:
            try:
                await self.bot.load_extension(ext)
            except commands.ExtensionAlreadyLoaded:
                continue

            if ext == "tasks.clock":
                await self.bot.change_presence(
                    status=discord.Status.idle,
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
            try:
                await self.bot.unload_extension(ext)
            except commands.ExtensionNotLoaded:
                continue

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
            for module in STATIC_MODULES:
                importlib.reload(sys.modules[module])
        else:
            for ext in extensions:
                if ext not in EXTENSIONS:
                    await msg.edit(content=f"Invalid extension: {ext}")
                    return

        for ext in extensions:
            try:
                await self.bot.reload_extension(ext)
            except commands.ExtensionNotLoaded:
                continue

            if ext == "tasks.clock":
                await self.bot.change_presence(
                    status=discord.Status.idle,
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

    @commands.command()
    @commands.is_owner()
    async def pprint(self, ctx: commands.Context, *, message: str) -> None:
        if ctx.channel.id != STATUS_CHANNEL:
            return

        pprint(self.eval(message))

    @commands.command()
    @commands.is_owner()
    async def rename(
        self,
        ctx: commands.Context,
        game: str,
        old_name: Annotated[str, lambda s: s.strip()],
        new_name: Annotated[str, lambda s: s.strip()],
    ) -> None:
        if (
            ctx.channel.id != STATUS_CHANNEL
            or game not in GAMES
            or not old_name
            or not new_name
        ):
            return

        game_details = GAMES[game]
        text = f"Renaming {old_name} to {new_name} in {game_details["name"]}..."
        msg = await ctx.send(text)
        cog = self.bot.get_cog("GoogleSheets")

        if game_details["infoReplaceGrid"]:
            await msg.edit(content=f"{text}\nEditing info sheet...")
            cog.find_replace_sheet_data(
                game_details["infoSpreadsheet"],
                game_details["infoReplaceGrid"],
                old_name,
                new_name,
                "kr" if game_details["timezone"] == TIMEZONES["KST"] else None,
            )
        if game_details["pingReplaceGrid"]:
            await msg.edit(content=f"{text}\nEditing ping sheet...")
            cog.find_replace_sheet_data(
                game_details["pingSpreadsheet"],
                game_details["pingReplaceGrid"],
                old_name,
                new_name,
                "kr" if game_details["timezone"] == TIMEZONES["KST"] else None,
            )
        if game_details["bonusReplaceGrid"]:
            await msg.edit(content=f"{text}\nEditing bonus sheet...")
            cog.find_replace_sheet_data(
                game_details["bonusSpreadsheet"],
                game_details["bonusReplaceGrid"],
                old_name,
                new_name,
                "kr" if game_details["timezone"] == TIMEZONES["KST"] else None,
            )
        if game_details["pinChannelIds"]:
            await msg.edit(content=f"{text}\nEditing last appearance data...")
            if old_name in self.bot.ssleague[game]:
                self.bot.ssleague[game][new_name] = self.bot.ssleague[game].pop(
                    old_name
                )
            if (
                game in self.bot.ssleague_manual
                and self.bot.ssleague_manual[game]["artist"] == old_name
            ):
                self.bot.ssleague_manual[game]["artist"] = new_name

                cog = self.bot.get_cog("DataSync")
                cog.save_ssleague_data()

        await msg.edit(content=f"{text}\nDownloading info data...")
        self.bot.info_data_ready = False
        cog = self.bot.get_cog("InfoSync")
        await cog.get_info_data(game, game_details)
        self.bot.info_data_ready = True

        await msg.edit(content=f"{text}\nDownloading bonus data...")
        self.bot.bonus_data_ready = False
        cog = self.bot.get_cog("BonusSync")
        await cog.get_bonus_data(game, game_details)
        self.bot.bonus_data_ready = True

        await msg.edit(
            content=f"Renamed {old_name} to {new_name} in {game_details["name"]}!"
        )


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Administrative(bot))
