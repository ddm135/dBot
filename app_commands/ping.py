import json
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from statics.consts import PING_DATA

if TYPE_CHECKING:
    from dBot import dBot


@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
class Ping(commands.GroupCog, name="ping", description="Manage words pings"):
    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    @app_commands.command(name="add")
    async def word_add(
        self,
        itr: discord.Interaction["dBot"],
        word: str,
    ) -> None:
        """Add a word to be pinged for

        Parameters
        -----------
        word: :class:`str`
            Word to be pinged for
        """
        await itr.response.defer(ephemeral=True)
        guild_id = str(itr.guild_id)
        user_id = str(itr.user.id)
        if user_id in self.bot.pings[guild_id][word]:
            return await itr.followup.send(
                f"You are already pinged for `{word}` in this server."
            )
        self.bot.pings[guild_id][word][user_id]["users"] = []
        self.bot.pings[guild_id][word][user_id]["channels"] = []
        with open(PING_DATA, "w") as f:
            json.dump(self.bot.pings, f, indent=4)
        return await itr.followup.send(
            f"Added to the ping list for `{word}` in this server!"
        )

    @app_commands.command(name="remove")
    async def word_remove(
        self,
        itr: discord.Interaction["dBot"],
        word: str,
    ) -> None:
        """Remove a word from the ping list

        Parameters
        -----------
        word: :class:`str`
            Word to be removed from the ping list
        """
        await itr.response.defer(ephemeral=True)
        guild_id = str(itr.guild_id)
        user_id = str(itr.user.id)
        if user_id not in self.bot.pings[guild_id][word]:
            return await itr.followup.send(
                f"You are not pinged for `{word}` in this server."
            )
        self.bot.pings[guild_id][word].pop(user_id)
        if not self.bot.pings[guild_id][word]:
            self.bot.pings[guild_id].pop(word)
        if not self.bot.pings[guild_id]:
            self.bot.pings.pop(guild_id)
        with open(PING_DATA, "w") as f:
            json.dump(self.bot.pings, f, indent=4)
        return await itr.followup.send(
            f"Removed from the ping list for `{word}` in this server!"
        )

    word_ignore = app_commands.Group(
        name="ignore",
        description="Ignore an user or channel for one or all current word pings",
    )

    @word_ignore.command(name="user")
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
        if word:
            if user_id not in self.bot.pings[guild_id][word]:
                return await itr.followup.send(
                    f"You are not pinged for `{word}` in this server."
                )
            if user.id in self.bot.pings[guild_id][word][user_id]["users"]:
                return await itr.followup.send(
                    f"You are already ignoring {user.mention} "
                    f"for `{word}` in this server."
                )
            self.bot.pings[guild_id][word][user_id]["users"].append(user.id)
            with open(PING_DATA, "w") as f:
                json.dump(self.bot.pings, f, indent=4)
            return await itr.followup.send(
                f"Added {user.mention} to the ignore list "
                f"for `{word}` in this server!"
            )
        else:
            for word in self.bot.pings[guild_id]:
                if user_id not in self.bot.pings[guild_id][word]:
                    continue

                if user.id in self.bot.pings[guild_id][word][user_id]["users"]:
                    continue

                self.bot.pings[guild_id][word][user_id]["users"].append(user.id)

            with open(PING_DATA, "w") as f:
                json.dump(self.bot.pings, f, indent=4)
            return await itr.followup.send(
                f"Added {user.mention} to the ignore list "
                f"for all current word pings in this server!"
            )

    @word_ignore.command(name="channel")
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
        if word:
            if user_id not in self.bot.pings[guild_id][word]:
                return await itr.followup.send(
                    f"You are not pinged for `{word}` in this server."
                )
            if channel.id in self.bot.pings[guild_id][word][user_id]["channels"]:
                return await itr.followup.send(
                    f"You are already ignoring {channel.mention} "
                    f"for `{word}` in this server."
                )
            self.bot.pings[guild_id][word][user_id]["channels"].append(channel.id)
            with open(PING_DATA, "w") as f:
                json.dump(self.bot.pings, f, indent=4)
            return await itr.followup.send(
                f"Added {channel.mention} to the ignore list "
                f"for `{word}` in this server!"
            )
        else:
            for word in self.bot.pings[guild_id]:
                if user_id not in self.bot.pings[guild_id][word]:
                    continue

                if channel.id in self.bot.pings[guild_id][word][user_id]["channels"]:
                    continue

                self.bot.pings[guild_id][word][user_id]["channels"].append(channel.id)

            with open(PING_DATA, "w") as f:
                json.dump(self.bot.pings, f, indent=4)
            return await itr.followup.send(
                f"Added {channel.mention} to the ignore list "
                f"for all current word pings in this server!"
            )

    word_unignore = app_commands.Group(
        name="unignore",
        description="Unignore an user or channel for one or all current word pings",
    )

    @word_unignore.command(name="user")
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
        if word:
            if user_id not in self.bot.pings[guild_id][word]:
                return await itr.followup.send(
                    f"You are not pinged for `{word}` in this server."
                )
            if user.id not in self.bot.pings[guild_id][word][user_id]["users"]:
                return await itr.followup.send(
                    f"You are not ignoring {user.mention} "
                    f"for `{word}` in this server."
                )
            self.bot.pings[guild_id][word][user_id]["users"].remove(user.id)
            with open(PING_DATA, "w") as f:
                json.dump(self.bot.pings, f, indent=4)
            return await itr.followup.send(
                f"Removed {user.mention} from the ignore list "
                f"for `{word}` in this server!"
            )
        else:
            for word in self.bot.pings[guild_id]:
                if user_id not in self.bot.pings[guild_id][word]:
                    continue

                if user.id not in self.bot.pings[guild_id][word][user_id]["users"]:
                    continue

                self.bot.pings[guild_id][word][user_id]["users"].remove(user.id)

            with open(PING_DATA, "w") as f:
                json.dump(self.bot.pings, f, indent=4)
            return await itr.followup.send(
                f"Removed {user.mention} from the ignore list "
                f"for all current word pings in this server!"
            )

    @word_unignore.command(name="channel")
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
        if word:
            if user_id not in self.bot.pings[guild_id][word]:
                return await itr.followup.send(
                    f"You are not pinged for `{word}` in this server."
                )
            if channel.id not in self.bot.pings[guild_id][word][user_id]["channels"]:
                return await itr.followup.send(
                    f"You are not ignoring {channel.mention} "
                    f"for `{word}` in this server."
                )
            self.bot.pings[guild_id][word][user_id]["channels"].remove(channel.id)
            with open(PING_DATA, "w") as f:
                json.dump(self.bot.pings, f, indent=4)
            return await itr.followup.send(
                f"Removed {channel.mention} from the ignore list "
                f"for `{word}` in this server!"
            )
        else:
            for word in self.bot.pings[guild_id]:
                if user_id not in self.bot.pings[guild_id][word]:
                    continue

                if (
                    channel.id
                    not in self.bot.pings[guild_id][word][user_id]["channels"]
                ):
                    continue

                self.bot.pings[guild_id][word][user_id]["channels"].remove(channel.id)

            with open(PING_DATA, "w") as f:
                json.dump(self.bot.pings, f, indent=4)
            return await itr.followup.send(
                f"Removed {channel.mention} from the ignore list "
                f"for all current word pings in this server!"
            )


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Ping(bot))
