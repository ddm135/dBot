"""``/ping``: word pings, and the listener that sends them."""

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from cogs.common import Itr
from db.word_pings import IgnoreKind, Subscription, WordPings, normalize
from ui.text import truncate

if TYPE_CHECKING:
    from bot import dBot

logger = logging.getLogger(__name__)

DESCRIPTION_LIMIT = 4096


def recipients(
    matches: list[tuple[str, dict[int, Subscription]]], author_id: int, channel_id: int
) -> list[tuple[str, int]]:
    """``(word, user_id)`` pairs to ping for a message.

    Authors are never pinged for their own message, and a user is skipped for
    a word when they ignore the author or the channel. A user is pinged once
    per message, for the first word that matches.
    """
    seen: set[int] = set()
    result = []
    for word, users in matches:
        for user_id, sub in users.items():
            if (
                user_id == author_id
                or user_id in seen
                or sub.ignores(author_id, channel_id)
            ):
                continue
            seen.add(user_id)
            result.append((word, user_id))
    return result


def ping_embed(word: str, message: discord.Message) -> discord.Embed:
    """The message that matched a word as an embed, linking back to it."""
    assert message.guild
    description = (
        f"`{message.author.name}` mentioned `{word}` in <#{message.channel.id}> on "
        f"<t:{int(message.created_at.timestamp())}:f>\n\n{message.content}"
    )
    embed = discord.Embed(
        description=truncate(description, DESCRIPTION_LIMIT), color=message.author.color
    )
    embed.set_author(
        name=f"Word Ping in {message.guild.name}",
        url=message.jump_url,
        icon_url=message.guild.icon.url if message.guild.icon else None,
    )
    embed.set_footer(text="Click title to jump to message")
    embed.set_thumbnail(url=message.author.display_avatar.url)
    return embed


@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.allowed_installs(guilds=True, users=False)
class Ping(commands.GroupCog, name="ping", description="Manage word pings"):
    """``/ping``: word pings. Users add words (per server) and get a DM when someone
    says them; users and channels can be ignored for all of a user's words or one.
    """

    def __init__(self, bot: dBot) -> None:
        self.bot = bot

    @property
    def book(self) -> WordPings:
        return self.bot.db.word_pings

    async def word_autocomplete(
        self, itr: Itr, current: str
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for a word: the user's own words in this server that match."""
        if itr.guild_id is None:
            return []
        wanted = normalize(current)
        words = self.book.words_of(itr.guild_id, itr.user.id)
        return [
            app_commands.Choice(name=w[:100], value=w[:100])
            for w in sorted(words)
            if wanted in w
        ][:25]

    # -- the listener --------------------------------------------------------

    @commands.Cog.listener("on_message")
    async def word_ping(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot or not message.content:
            return
        matches = self.book.matches(message.guild.id, message.content)
        for word, user_id in recipients(matches, message.author.id, message.channel.id):
            await self._send(message, word, user_id)

    async def _send(self, message: discord.Message, word: str, user_id: int) -> None:
        guild = message.guild
        assert guild
        try:
            member = guild.get_member(user_id) or await guild.fetch_member(user_id)
        except discord.NotFound:
            return  # they left the server
        except discord.HTTPException:
            logger.debug("Could not look up member %d.", user_id, exc_info=True)
            return
        # Never leak a channel to someone who cannot read it.
        if not message.channel.permissions_for(member).read_message_history:
            return
        try:
            await member.send(embed=ping_embed(word, message))
        except discord.Forbidden, discord.NotFound:
            return
        except discord.HTTPException:
            logger.warning("Could not send a word ping to %d.", user_id, exc_info=True)
            return
        await self.book.record_ping(guild.id, user_id, word)

    # -- commands ------------------------------------------------------------

    @app_commands.command(name="add")
    async def word_add(self, itr: Itr, word: str) -> None:
        """Add a word to the ping list

        Parameters
        ----------
        word: Word to add to the ping list
        """
        assert itr.guild_id
        try:
            added = await self.book.add(itr.guild_id, itr.user.id, word)
        except ValueError:
            await itr.response.send_message(
                "A word must be between 1 and 100 characters.", ephemeral=True
            )
            return
        word = normalize(word)
        text = (
            f"Added to the ping list for `{word}` in this server!"
            if added
            else f"You are already pinged for `{word}` in this server."
        )
        await itr.response.send_message(text, ephemeral=True)

    @app_commands.command(name="remove")
    @app_commands.autocomplete(word=word_autocomplete)
    async def word_remove(self, itr: Itr, word: str) -> None:
        """Remove a word from the ping list

        Parameters
        ----------
        word: Word to remove from the ping list
        """
        assert itr.guild_id
        removed = await self.book.remove(itr.guild_id, itr.user.id, word)
        word = normalize(word)
        text = (
            f"Removed from the ping list for `{word}` in this server!"
            if removed
            else f"You are not pinged for `{word}` in this server."
        )
        await itr.response.send_message(text, ephemeral=True)

    @app_commands.command(name="list")
    async def word_list(self, itr: Itr) -> None:
        """List all ping words and their ping count"""
        assert itr.guild and itr.guild_id
        words = self.book.words_of(itr.guild_id, itr.user.id)
        embed = discord.Embed(
            title=f"Word Pings in {itr.guild.name}",
            color=itr.user.color,
        )
        if not words:
            embed.description = "You have no word pings in this server."
        for word, sub in sorted(words.items())[:25]:
            ignored = [f"<@{u}>" for u in sorted(sub.users)] + [
                f"<#{c}>" for c in sorted(sub.channels)
            ]
            value = f"Pinged {sub.count:,} time{'s' if sub.count != 1 else ''}"
            if ignored:
                value += "\nIgnoring: " + truncate(", ".join(ignored), 900)
            embed.add_field(name=word[:256], value=value, inline=False)
        await itr.response.send_message(embed=embed, ephemeral=True)

    ignore = app_commands.Group(
        name="ignore",
        description="Ignore a user or channel for one or all current word pings",
    )
    unignore = app_commands.Group(
        name="unignore",
        description="Unignore a user or channel for one or all current word pings",
    )

    async def _change(
        self,
        itr: Itr,
        kind: IgnoreKind,
        target: discord.abc.Snowflake,
        mention: str,
        word: str | None,
        *,
        add: bool,
    ) -> None:
        assert itr.guild_id
        guild_id, user_id = itr.guild_id, itr.user.id
        if kind == "user" and target.id == user_id:
            verb = "ignore" if add else "unignore"
            await itr.response.send_message(
                f"You cannot {verb} yourself.", ephemeral=True
            )
            return
        if word is not None and self.book.get(guild_id, user_id, word) is None:
            await itr.response.send_message(
                f"You are not pinged for `{normalize(word)}` in this server.",
                ephemeral=True,
            )
            return
        change = self.book.ignore if add else self.book.unignore
        changed = await change(guild_id, user_id, kind, target.id, word)
        scope = f"for `{normalize(word)}`" if word else "for all current word pings"
        if not changed:
            state = "already ignoring" if add else "not ignoring"
            await itr.response.send_message(
                f"You are {state} {mention} {scope} in this server.", ephemeral=True
            )
            return
        action = "Added" if add else "Removed"
        direction = "to" if add else "from"
        await itr.response.send_message(
            f"{action} {mention} {direction} the ignore list {scope} in this server!",
            ephemeral=True,
        )

    @ignore.command(name="user")
    @app_commands.autocomplete(word=word_autocomplete)
    async def ignore_user(
        self, itr: Itr, user: discord.User, word: str | None = None
    ) -> None:
        """Ignore a user for one or all current word pings

        Parameters
        ----------
        user: User to be ignored
        word: Word to be ignored. If unspecified, all current word pings
        """
        await self._change(itr, "user", user, user.mention, word, add=True)

    @ignore.command(name="channel")
    @app_commands.autocomplete(word=word_autocomplete)
    async def ignore_channel(
        self, itr: Itr, channel: discord.TextChannel, word: str | None = None
    ) -> None:
        """Ignore a channel for one or all current word pings

        Parameters
        ----------
        channel: Channel to be ignored
        word: Word to be ignored. If unspecified, all current word pings
        """
        await self._change(itr, "channel", channel, channel.mention, word, add=True)

    @unignore.command(name="user")
    @app_commands.autocomplete(word=word_autocomplete)
    async def unignore_user(
        self, itr: Itr, user: discord.User, word: str | None = None
    ) -> None:
        """Unignore a user for one or all current word pings

        Parameters
        ----------
        user: User to be unignored
        word: Word to be unignored. If unspecified, all current word pings
        """
        await self._change(itr, "user", user, user.mention, word, add=False)

    @unignore.command(name="channel")
    @app_commands.autocomplete(word=word_autocomplete)
    async def unignore_channel(
        self, itr: Itr, channel: discord.TextChannel, word: str | None = None
    ) -> None:
        """Unignore a channel for one or all current word pings

        Parameters
        ----------
        channel: Channel to be unignored
        word: Word to be unignored. If unspecified, all current word pings
        """
        await self._change(itr, "channel", channel, channel.mention, word, add=False)


async def setup(bot: dBot) -> None:
    await bot.add_cog(Ping(bot))
