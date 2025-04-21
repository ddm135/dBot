import json
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from app_commands.autocomplete.ping import word_autocomplete
from statics.consts import PING_DATA
from statics.types import PingDetails

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
        if self.bot.pings[guild_id][word][user_id]:
            return await itr.followup.send(
                f"You are already pinged for `{word}` in this server."
            )
        self.bot.pings[guild_id][word][user_id] = PingDetails(
            users=[], channels=[], count=0
        )
        self.save_ping_data()
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
            Word to be removed from the ping list
        """
        await itr.response.defer(ephemeral=True)
        guild_id = str(itr.guild_id)
        user_id = str(itr.user.id)
        if not self.bot.pings[guild_id][word][user_id]:
            return await itr.followup.send(
                f"You are not pinged for `{word}` in this server."
            )
        self.bot.pings[guild_id][word].pop(user_id)
        self.save_ping_data()
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
        guild_id = str(itr.guild_id)
        user_id = str(itr.user.id)
        description = ""
        for word in self.bot.pings[guild_id]:
            if not self.bot.pings[guild_id][word][user_id]:
                continue

            description += (
                f"`{word}` - pinged "
                f"`{self.bot.pings[guild_id][word][user_id].setdefault("count", 0)}`"
                f"{(" times"
                    if self.bot.pings[guild_id][word][user_id]["count"] > 1
                    else " time")}\n"
            )

        if not description:
            description = "None"
        else:
            description = description[:-1]

        assert itr.guild
        embed = discord.Embed(
            description=description,
            color=itr.user.color,
        )
        embed.set_author(
            name=f"Word Pings in {itr.guild.name}",
            icon_url=itr.guild.icon.url if itr.guild.icon else None,
        )

        await itr.user.send(embed=embed)
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
        if word is not None:
            if user.id == itr.user.id:
                return await itr.followup.send("You cannot ignore yourself.")
            if not self.bot.pings[guild_id][word][user_id]:
                return await itr.followup.send(
                    f"You are not pinged for `{word}` in this server."
                )
            if user.id in self.bot.pings[guild_id][word][user_id]["users"]:
                return await itr.followup.send(
                    f"You are already ignoring {user.mention} "
                    f"for `{word}` in this server."
                )
            self.bot.pings[guild_id][word][user_id]["users"].append(user.id)
            self.save_ping_data()
            return await itr.followup.send(
                f"Added {user.mention} to the ignore list "
                f"for `{word}` in this server!"
            )
        else:
            for word in self.bot.pings[guild_id]:
                if not self.bot.pings[guild_id][word][user_id]:
                    continue

                if user.id in self.bot.pings[guild_id][word][user_id]["users"]:
                    continue

                self.bot.pings[guild_id][word][user_id]["users"].append(user.id)

            self.save_ping_data()
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
        if word is not None:
            if not self.bot.pings[guild_id][word][user_id]:
                return await itr.followup.send(
                    f"You are not pinged for `{word}` in this server."
                )
            if channel.id in self.bot.pings[guild_id][word][user_id]["channels"]:
                return await itr.followup.send(
                    f"You are already ignoring {channel.mention} "
                    f"for `{word}` in this server."
                )
            self.bot.pings[guild_id][word][user_id]["channels"].append(channel.id)
            self.save_ping_data()
            return await itr.followup.send(
                f"Added {channel.mention} to the ignore list "
                f"for `{word}` in this server!"
            )
        else:
            for word in self.bot.pings[guild_id]:
                if not self.bot.pings[guild_id][word][user_id]:
                    continue

                if channel.id in self.bot.pings[guild_id][word][user_id]["channels"]:
                    continue

                self.bot.pings[guild_id][word][user_id]["channels"].append(channel.id)

            self.save_ping_data()
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
        if word is not None:
            if user.id == itr.user.id:
                return await itr.followup.send("You cannot unignore yourself.")
            if not self.bot.pings[guild_id][word][user_id]:
                return await itr.followup.send(
                    f"You are not pinged for `{word}` in this server."
                )
            if user.id not in self.bot.pings[guild_id][word][user_id]["users"]:
                return await itr.followup.send(
                    f"You are not ignoring {user.mention} "
                    f"for `{word}` in this server."
                )
            self.bot.pings[guild_id][word][user_id]["users"].remove(user.id)
            self.save_ping_data()
            return await itr.followup.send(
                f"Removed {user.mention} from the ignore list "
                f"for `{word}` in this server!"
            )
        else:
            for word in self.bot.pings[guild_id]:
                if not self.bot.pings[guild_id][word][user_id]:
                    continue

                if user.id not in self.bot.pings[guild_id][word][user_id]["users"]:
                    continue

                self.bot.pings[guild_id][word][user_id]["users"].remove(user.id)

            self.save_ping_data()
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
        if word is not None:
            if not self.bot.pings[guild_id][word][user_id]:
                return await itr.followup.send(
                    f"You are not pinged for `{word}` in this server."
                )
            if channel.id not in self.bot.pings[guild_id][word][user_id]["channels"]:
                return await itr.followup.send(
                    f"You are not ignoring {channel.mention} "
                    f"for `{word}` in this server."
                )
            self.bot.pings[guild_id][word][user_id]["channels"].remove(channel.id)
            self.save_ping_data()
            return await itr.followup.send(
                f"Removed {channel.mention} from the ignore list "
                f"for `{word}` in this server!"
            )
        else:
            for word in self.bot.pings[guild_id]:
                if not self.bot.pings[guild_id][word][user_id]:
                    continue

                if (
                    channel.id
                    not in self.bot.pings[guild_id][word][user_id]["channels"]
                ):
                    continue

                self.bot.pings[guild_id][word][user_id]["channels"].remove(channel.id)

            self.save_ping_data()
            return await itr.followup.send(
                f"Removed {channel.mention} from the ignore list "
                f"for all current word pings in this server!"
            )

    def save_ping_data(self) -> None:
        with open(PING_DATA, "w") as f:
            json.dump(self.bot.pings, f, indent=4)


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Ping(bot))
