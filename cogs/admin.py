"""Owner commands, usable only in the status channel."""

import logging
from typing import TYPE_CHECKING, Literal

import discord
from discord.ext import commands

from channels import find_channel
from discord_ids import STATUS_CHANNEL_ID
from extensions import EXTENSIONS
from games.registry import GAMES

if TYPE_CHECKING:
    from bot import dBot

logger = logging.getLogger(__name__)

type Ctx = commands.Context[dBot]

CLOCK = "tasks.clock"
GIT_TIMEOUT = 60.0


def _in_status_channel(ctx: Ctx) -> bool:
    return ctx.channel.id == STATUS_CHANNEL_ID


class Administrative(commands.Cog):
    def __init__(self, bot: dBot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: Ctx) -> bool:  # type: ignore[override]
        return await self.bot.is_owner(ctx.author) and _in_status_channel(ctx)

    @commands.command()
    async def delete(self, ctx: Ctx, channel_id: int, message_id: int) -> None:
        channel = await find_channel(self.bot, channel_id, discord.abc.Messageable)
        if channel is None:
            return
        try:
            await (await channel.fetch_message(message_id)).delete()
        except discord.HTTPException:
            logger.debug("Could not delete the message.", exc_info=True)

    @commands.command()
    async def sync(self, ctx: Ctx) -> None:
        msg = await ctx.send("Syncing app commands...")
        try:
            await self.bot.tree.sync()
        except discord.RateLimited:
            await msg.edit(content="Rate limited.")
        else:
            await msg.edit(content="Synced!")

    @commands.command()
    async def echo(self, ctx: Ctx, *, message: str) -> None:
        await ctx.send(message)

    # -- extensions ----------------------------------------------------------

    async def _each(
        self,
        ctx: Ctx,
        action: Literal["load", "unload", "reload"],
        names: tuple[str, ...],
    ) -> None:
        names = names or EXTENSIONS
        invalid = [n for n in names if n not in EXTENSIONS]
        if invalid:
            await ctx.send(f"Invalid extension: {', '.join(invalid)}")
            return
        msg = await ctx.send(f"{action.title()}ing extensions...")
        operation = getattr(self.bot, f"{action}_extension")
        errors: list[str] = []
        for name in names:
            try:
                await operation(name)
            except commands.ExtensionAlreadyLoaded, commands.ExtensionNotLoaded:
                continue
            except commands.ExtensionError as exc:
                logger.exception("Could not %s %s.", action, name)
                errors.append(f"{name}: {exc.__class__.__name__}")
                continue
            if name == CLOCK:
                await self._clock_presence(action)
        await msg.edit(
            content=f"{action.title()}ed!"
            + ("\n" + "\n".join(errors) if errors else "")
        )

    async def _clock_presence(self, action: str) -> None:
        if action == "unload":
            await self.bot.change_presence(
                status=discord.Status.dnd,
                activity=discord.CustomActivity("Clock is disabled."),
            )
        else:
            await self.bot.change_presence(
                status=discord.Status.idle,
                activity=discord.CustomActivity("Waiting for clock..."),
            )

    @commands.command()
    async def load(self, ctx: Ctx, *extensions: str) -> None:
        await self._each(ctx, "load", extensions)

    @commands.command()
    async def unload(self, ctx: Ctx, *extensions: str) -> None:
        await self._each(ctx, "unload", extensions)

    @commands.command()
    async def reload(self, ctx: Ctx, *extensions: str) -> None:
        await self._each(ctx, "reload", extensions)

    # -- data ----------------------------------------------------------------

    @commands.command()
    async def resync(self, ctx: Ctx) -> None:
        """Run the hourly game data syncs now."""
        msg = await ctx.send("Syncing game data...")
        failed = await self.bot.games.sync_basic()
        failed += [k for k in await self.bot.games.sync_tables() if k not in failed]
        await msg.edit(
            content="Synced!" if not failed else f"Incomplete for: {', '.join(failed)}"
        )

    @commands.group(invoke_without_command=True)
    async def alias(self, ctx: Ctx) -> None:
        await ctx.send("Use `alias list|add|remove <game> <song|deck> <code> [alias]`.")

    async def _alias_target(
        self, ctx: Ctx, game: str, kind: str, code: int
    ) -> tuple[str, Literal["song", "deck"]] | None:
        game = game.upper()
        index = self.bot.indexes.get(game) if game in GAMES else None
        if index is None or kind not in ("song", "deck"):
            await ctx.send("Unknown game or kind.")
            return None
        known = index.decks.songs if kind == "song" else index.decks.decks
        if code not in known:
            await ctx.send(f"There is no {kind} {code} in {game}.")
            return None
        return game, kind  # type: ignore[return-value]

    @alias.command(name="list")  # type: ignore[arg-type]
    async def alias_list(self, ctx: Ctx, game: str, kind: str, code: int) -> None:
        if target := await self._alias_target(ctx, game, kind, code):
            found = self.bot.search.aliases_of(target[0], target[1], code)
            await ctx.send(", ".join(f"`{a}`" for a in found) or "No aliases.")

    @alias.command(name="add")  # type: ignore[arg-type]
    async def alias_add(
        self, ctx: Ctx, game: str, kind: str, code: int, *, alias: str
    ) -> None:
        if target := await self._alias_target(ctx, game, kind, code):
            added = await self.bot.search.add_alias(target[0], target[1], code, alias)
            await ctx.send("Added." if added else "That alias already exists.")

    @alias.command(name="remove")  # type: ignore[arg-type]
    async def alias_remove(
        self, ctx: Ctx, game: str, kind: str, code: int, *, alias: str
    ) -> None:
        if target := await self._alias_target(ctx, game, kind, code):
            removed = await self.bot.search.remove_alias(
                target[0], target[1], code, alias
            )
            await ctx.send("Removed." if removed else "No such alias.")

    @commands.group(name="name", invoke_without_command=True)
    async def display_name(self, ctx: Ctx) -> None:
        await ctx.send("Use `name list|set|clear <game> <song|deck> <code> [name]`.")

    @display_name.command(name="list")  # type: ignore[arg-type]
    async def name_list(self, ctx: Ctx, game: str) -> None:
        game = game.upper()
        if game not in GAMES:
            await ctx.send("Unknown game.")
            return
        found = await self.bot.db.display_names.all(game)
        await ctx.send(
            "\n".join(f"{kind} {code}: {name}" for (kind, code), name in found.items())
            or "No custom names."
        )

    @display_name.command(name="set")  # type: ignore[arg-type]
    async def name_set(
        self, ctx: Ctx, game: str, kind: str, code: int, *, name: str
    ) -> None:
        if target := await self._alias_target(ctx, game, kind, code):
            await self.bot.db.display_names.set(target[0], target[1], code, name)
            await self._reload_names(target[0])
            await ctx.send("Set.")

    @display_name.command(name="clear")  # type: ignore[arg-type]
    async def name_clear(self, ctx: Ctx, game: str, kind: str, code: int) -> None:
        if target := await self._alias_target(ctx, game, kind, code):
            cleared = await self.bot.db.display_names.clear(target[0], target[1], code)
            await self._reload_names(target[0])
            await ctx.send("Cleared." if cleared else "That one had no custom name.")

    async def _reload_names(self, game: str) -> None:
        self.bot.indexes.set_names(game, await self.bot.db.display_names.all(game))


async def setup(bot: dBot) -> None:
    await bot.add_cog(Administrative(bot))
