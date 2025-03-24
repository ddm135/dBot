import json
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from statics.consts import PING_DATA

if TYPE_CHECKING:
    from dBot import dBot


@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
class Ping(commands.GroupCog, name="ping", description="Manage Word Pings"):
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
        with open(PING_DATA, "w") as f:
            json.dump(self.bot.pings, f, indent=4)
        return await itr.followup.send(
            f"Removed from the ping list for `{word}` in this server!"
        )


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Ping(bot))
