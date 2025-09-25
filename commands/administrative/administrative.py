import asyncio
import importlib
import logging
import sys
from pprint import pprint
from typing import TYPE_CHECKING, Annotated

import discord
from asteval import Interpreter  # type: ignore[import-untyped]
from discord.ext import commands

from statics.consts import EXTENSIONS, GAMES, STATIC_MODULES, STATUS_CHANNEL, Data

if TYPE_CHECKING:
    from dBot import dBot
    from helpers.google_sheets import GoogleSheets
    from tasks.bonus_sync import BonusSync
    from tasks.data_sync import DataSync
    from tasks.emblem_sync import EmblemSync
    from tasks.info_sync import InfoSync


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
    async def delete(
        self, ctx: commands.Context, channel_id: int, message_id: int
    ) -> None:
        if ctx.channel.id != STATUS_CHANNEL:
            return

        try:
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(
                channel_id
            )
            assert isinstance(channel, discord.TextChannel)
            message = await channel.fetch_message(message_id)
            await message.delete()
        except Exception:
            pass

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
            or not old_name
            or not new_name
            or not (game_details := GAMES.get(game))
        ):
            return

        text = f"Renaming {old_name} to {new_name} in {game_details["name"]}..."
        msg = await ctx.send(text)
        sheets_cog: "GoogleSheets" = self.bot.get_cog(
            "GoogleSheets"
        )  # type: ignore[assignment]

        for data in ("info", "bonus", "ping", "emblem"):
            if (details := game_details.get(data)) and (
                replace_grid := details["replaceGrid"]  # type: ignore[index]
            ):
                await msg.edit(content=f"{text}\nEditing {data} sheet...")
                await sheets_cog.find_replace_sheet_data(
                    details["spreadsheetId"],  # type: ignore[index]
                    replace_grid,
                    old_name,
                    new_name,
                )
        if game_details["pinChannelIds"]:
            await msg.edit(content=f"{text}\nEditing last appearance data...")
            if old_name in self.bot.ssleagues[game]:
                self.bot.ssleagues[game][new_name] = self.bot.ssleagues[game].pop(
                    old_name
                )
            if (
                game in self.bot.ssleague_manual
                and self.bot.ssleague_manual[game]["artist"] == old_name
            ):
                self.bot.ssleague_manual[game]["artist"] = new_name

                data_cog: "DataSync" = self.bot.get_cog(
                    "DataSync"
                )  # type: ignore[assignment]
                data_cog.save_data(Data.SSLEAGUES)

        await msg.edit(content=f"{text}\nDownloading info data...")
        info_cog: "InfoSync" = self.bot.get_cog("InfoSync")  # type: ignore[assignment]
        await info_cog.get_info_data(game, game_details)

        await msg.edit(content=f"{text}\nDownloading bonus data...")
        bonus_cog: "BonusSync" = self.bot.get_cog(
            "BonusSync"
        )  # type: ignore[assignment]
        await bonus_cog.get_bonus_data(game, game_details)

        await msg.edit(content=f"{text}\nDownloading emblem data...")
        emblem_cog: "EmblemSync" = self.bot.get_cog(
            "EmblemSync"
        )  # type: ignore[assignment]
        await emblem_cog.get_emblem_data(game, game_details)

        await msg.edit(
            content=f"Renamed {old_name} to {new_name} in {game_details["name"]}!"
        )


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Administrative(bot))
