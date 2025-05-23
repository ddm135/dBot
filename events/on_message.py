import importlib
import json
import re
import sys
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from statics.consts import PING_DATA

if (EMBEDS := "events.embeds.on_message") in sys.modules:
    importlib.reload(sys.modules[EMBEDS])
from events.embeds.on_message import WordPingEmbed

if TYPE_CHECKING:
    from dBot import dBot


class OnMessage(commands.Cog):
    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    @commands.Cog.listener("on_message")
    async def bonusBot_info(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        msg_content = message.content.lower()
        if (
            msg_content.startswith("h!i")
            and msg_content.endswith(("wakeone", "wo", "w1"))
            and message.channel.id == 401412343629742090
        ):
            await message.reply("Use dBot's `/info` instead.", mention_author=False)
            return

    @commands.Cog.listener("on_message")
    async def word_ping(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return

        guild_id = str(message.guild.id)
        for word in self.bot.pings[guild_id]:
            regexp = (
                rf"(?:(?:[\s!@#\$%\^&\*\(\)\-_=\+\[{{\]}}\\\\\|;:'\",<\.>\/\?])+|^)"
                rf"{re.escape(word)}"
                rf"(?:(?:[\s!@#\$%\^&\*\(\)\-_=\+\[{{\]}}\\\\\|;:'\",<\.>\/\?])+|$)"
            )
            if not re.search(regexp, message.content, flags=re.IGNORECASE):
                continue

            for user_id in self.bot.pings[guild_id][word]:
                user_id_int = int(user_id)
                if (
                    message.author.id == user_id_int
                    or not self.bot.pings[guild_id][word][user_id]
                    or message.author.id
                    in self.bot.pings[guild_id][word][user_id]["users"]
                    or message.channel.id
                    in self.bot.pings[guild_id][word][user_id]["channels"]
                ):
                    continue

                user = await self.bot.fetch_user(user_id_int)
                if not user:
                    continue

                self.bot.pings[guild_id][word][user_id]["count"] += 1
                with open(PING_DATA, "w") as f:
                    json.dump(self.bot.pings, f, indent=4)

                await user.send(embed=WordPingEmbed(word, message))


async def setup(bot: "dBot") -> None:
    await bot.add_cog(OnMessage(bot))
