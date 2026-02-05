# mypy: disable-error-code="assignment"
# pyright: reportAssignmentType=false

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from statics.consts import Data

from .autocompletes import word_autocomplete
from .embeds import WordPingsEmbed

if TYPE_CHECKING:
    from dBot import dBot
    from tasks.data_sync import DataSync


@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.allowed_installs(guilds=True, users=False)
class Ping(commands.GroupCog, name="ping", description="Manage words pings"):
    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    @app_commands.command(name="add")
    async def word_add(
        self,
        itr: discord.Interaction["dBot"],
        word: str,
    ) -> None:
        """Add a word to the ping list

        Parameters
        -----------
        word: :class:`str`
            Word to add to the ping list
        """
        await itr.response.defer(ephemeral=True)
        guild_id = str(itr.guild_id)
        user_id = str(itr.user.id)
        if self.bot.word_pings[guild_id][word][user_id]:
            return await itr.followup.send(
                f"You are already pinged for `{word}` in this server."
            )
        self.bot.word_pings[guild_id][word][user_id] = {
            "users": [],
            "channels": [],
            "count": 0,
        }

        cog: "DataSync" = self.bot.get_cog("DataSync")
        cog.save_data(Data.WORD_PINGS)
        return await itr.followup.send(
            f"Added to the ping list for `{word}` in this server!"
        )

    @app_commands.command(name="remove")
    @app_commands.autocomplete(word=word_autocomplete)
    async def word_remove(
        self,
        itr: discord.Interaction["dBot"],
        word: str,
    ) -> None:
        """Remove a word from the ping list

        Parameters
        -----------
        word: :class:`str`
            Word to remove from the ping list
        """
        await itr.response.defer(ephemeral=True)
        guild_id = str(itr.guild_id)
        user_id = str(itr.user.id)
        if not self.bot.word_pings[guild_id][word][user_id]:
            return await itr.followup.send(
                f"You are not pinged for `{word}` in this server."
            )
        self.bot.word_pings[guild_id][word].pop(user_id)

        cog: "DataSync" = self.bot.get_cog("DataSync")
        cog.save_data(Data.WORD_PINGS)
        return await itr.followup.send(
            f"Removed from the ping list for `{word}` in this server!"
        )

    @app_commands.command(name="list")
    async def word_list(
        self,
        itr: discord.Interaction["dBot"],
    ) -> None:
        """List all ping words and their ping count"""
        await itr.response.defer(ephemeral=True)

        assert itr.guild
        await itr.user.send(
            embed=WordPingsEmbed(
                itr.user, itr.guild, self.bot.word_pings[str(itr.guild_id)]
            )
        )
        return await itr.followup.send(
            "Check your DMs for the list of words you are pinged for!"
        )

    word_ignore = app_commands.Group(
        name="ignore",
        description="Ignore an user or channel for one or all current word pings",
    )

    @word_ignore.command(name="user")
    @app_commands.autocomplete(word=word_autocomplete)
    async def word_ignore_user(
        self,
        itr: discord.Interaction["dBot"],
        user: discord.User,
        word: str | None = None,
    ) -> None:
        """Ignore a user for one or all current word pings

        Parameters
        -----------
        user: :class:`discord.User`
            User to be ignored
        word: Optional[:class:`str`]
            Word to be ignored. If unspecified, all current word pings
            from this user will be ignored
        """
        await itr.response.defer(ephemeral=True)
        guild_id = str(itr.guild_id)
        user_id = str(itr.user.id)
        cog: "DataSync" = self.bot.get_cog("DataSync")

        if word is not None:
            if user.id == itr.user.id:
                return await itr.followup.send("You cannot ignore yourself.")
            if not self.bot.word_pings[guild_id][word][user_id]:
                return await itr.followup.send(
                    f"You are not pinged for `{word}` in this server."
                )
            if user.id in self.bot.word_pings[guild_id][word][user_id]["users"]:
                return await itr.followup.send(
                    f"You are already ignoring {user.mention} "
                    f"for `{word}` in this server."
                )
            self.bot.word_pings[guild_id][word][user_id]["users"].append(user.id)

            cog.save_data(Data.WORD_PINGS)
            return await itr.followup.send(
                f"Added {user.mention} to the ignore list "
                f"for `{word}` in this server!"
            )
        else:
            for word in self.bot.word_pings[guild_id]:
                if not self.bot.word_pings[guild_id][word][user_id]:
                    continue

                if user.id in self.bot.word_pings[guild_id][word][user_id]["users"]:
                    continue

                self.bot.word_pings[guild_id][word][user_id]["users"].append(user.id)

            cog.save_data(Data.WORD_PINGS)
            return await itr.followup.send(
                f"Added {user.mention} to the ignore list "
                f"for all current word pings in this server!"
            )

    @word_ignore.command(name="channel")
    @app_commands.autocomplete(word=word_autocomplete)
    async def word_ignore_channel(
        self,
        itr: discord.Interaction["dBot"],
        channel: discord.TextChannel,
        word: str | None = None,
    ) -> None:
        """Ignore a channel for one or all current word pings

        Parameters
        -----------
        channel: :class:`discord.TextChannel`
            Channel to be ignored
        word: Optional[:class:`str`]
            Word to be ignored. If unspecified, all current word pings
            in this channel will be ignored
        """
        await itr.response.defer(ephemeral=True)
        guild_id = str(itr.guild_id)
        user_id = str(itr.user.id)
        cog: "DataSync" = self.bot.get_cog("DataSync")

        if word is not None:
            if not self.bot.word_pings[guild_id][word][user_id]:
                return await itr.followup.send(
                    f"You are not pinged for `{word}` in this server."
                )
            if channel.id in self.bot.word_pings[guild_id][word][user_id]["channels"]:
                return await itr.followup.send(
                    f"You are already ignoring {channel.mention} "
                    f"for `{word}` in this server."
                )
            self.bot.word_pings[guild_id][word][user_id]["channels"].append(channel.id)

            cog.save_data(Data.WORD_PINGS)
            return await itr.followup.send(
                f"Added {channel.mention} to the ignore list "
                f"for `{word}` in this server!"
            )
        else:
            for word in self.bot.word_pings[guild_id]:
                if not self.bot.word_pings[guild_id][word][user_id]:
                    continue

                if (
                    channel.id
                    in self.bot.word_pings[guild_id][word][user_id]["channels"]
                ):
                    continue

                self.bot.word_pings[guild_id][word][user_id]["channels"].append(
                    channel.id
                )

            cog.save_data(Data.WORD_PINGS)
            return await itr.followup.send(
                f"Added {channel.mention} to the ignore list "
                f"for all current word pings in this server!"
            )

    word_unignore = app_commands.Group(
        name="unignore",
        description="Unignore an user or channel for one or all current word pings",
    )

    @word_unignore.command(name="user")
    @app_commands.autocomplete(word=word_autocomplete)
    async def word_unignore_user(
        self,
        itr: discord.Interaction["dBot"],
        user: discord.User,
        word: str | None = None,
    ) -> None:
        """Unignore a user for one or all current word pings

        Parameters
        -----------
        user: :class:`discord.User`
            User to be unignored
        word: Optional[:class:`str`]
            Word to be unignored. If unspecified, all current word pings
            from this user will no longer be ignored
        """
        await itr.response.defer(ephemeral=True)
        guild_id = str(itr.guild_id)
        user_id = str(itr.user.id)
        cog: "DataSync" = self.bot.get_cog("DataSync")

        if word is not None:
            if user.id == itr.user.id:
                return await itr.followup.send("You cannot unignore yourself.")
            if not self.bot.word_pings[guild_id][word][user_id]:
                return await itr.followup.send(
                    f"You are not pinged for `{word}` in this server."
                )
            if user.id not in self.bot.word_pings[guild_id][word][user_id]["users"]:
                return await itr.followup.send(
                    f"You are not ignoring {user.mention} "
                    f"for `{word}` in this server."
                )
            self.bot.word_pings[guild_id][word][user_id]["users"].remove(user.id)

            cog.save_data(Data.WORD_PINGS)
            return await itr.followup.send(
                f"Removed {user.mention} from the ignore list "
                f"for `{word}` in this server!"
            )
        else:
            for word in self.bot.word_pings[guild_id]:
                if not self.bot.word_pings[guild_id][word][user_id]:
                    continue

                if user.id not in self.bot.word_pings[guild_id][word][user_id]["users"]:
                    continue

                self.bot.word_pings[guild_id][word][user_id]["users"].remove(user.id)

            cog.save_data(Data.WORD_PINGS)
            return await itr.followup.send(
                f"Removed {user.mention} from the ignore list "
                f"for all current word pings in this server!"
            )

    @word_unignore.command(name="channel")
    @app_commands.autocomplete(word=word_autocomplete)
    async def word_unignore_channel(
        self,
        itr: discord.Interaction["dBot"],
        channel: discord.TextChannel,
        word: str | None = None,
    ) -> None:
        """Unignore a channel for one or all current word pings

        Parameters
        -----------
        channel: :class:`discord.TextChannel`
            Channel to be unignored
        word: Optional[:class:`str`]
            Word to be unignored. If unspecified, all current word pings
            in this channel will no longer be ignored
        """
        await itr.response.defer(ephemeral=True)
        guild_id = str(itr.guild_id)
        user_id = str(itr.user.id)
        cog: "DataSync" = self.bot.get_cog("DataSync")

        if word is not None:
            if not self.bot.word_pings[guild_id][word][user_id]:
                return await itr.followup.send(
                    f"You are not pinged for `{word}` in this server."
                )
            if (
                channel.id
                not in self.bot.word_pings[guild_id][word][user_id]["channels"]
            ):
                return await itr.followup.send(
                    f"You are not ignoring {channel.mention} "
                    f"for `{word}` in this server."
                )
            self.bot.word_pings[guild_id][word][user_id]["channels"].remove(channel.id)

            cog.save_data(Data.WORD_PINGS)
            return await itr.followup.send(
                f"Removed {channel.mention} from the ignore list "
                f"for `{word}` in this server!"
            )
        else:
            for word in self.bot.word_pings[guild_id]:
                if not self.bot.word_pings[guild_id][word][user_id]:
                    continue

                if (
                    channel.id
                    not in self.bot.word_pings[guild_id][word][user_id]["channels"]
                ):
                    continue

                self.bot.word_pings[guild_id][word][user_id]["channels"].remove(
                    channel.id
                )

            cog.save_data(Data.WORD_PINGS)
            return await itr.followup.send(
                f"Removed {channel.mention} from the ignore list "
                f"for all current word pings in this server!"
            )


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Ping(bot))
