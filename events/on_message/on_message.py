import re
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from .embeds import WordPingEmbed

if TYPE_CHECKING:
    from dBot import dBot


class OnMessage(commands.Cog):
    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

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

                try:
                    user = self.bot.get_user(user_id_int) or await self.bot.fetch_user(
                        user_id_int
                    )
                    await user.send(embed=WordPingEmbed(word, message))
                except (discord.NotFound, discord.Forbidden):
                    continue

                self.bot.pings[guild_id][word][user_id]["count"] += 1
                cog = self.bot.get_cog("DataSync")
                cog.save_ping_data()  # type: ignore[union-attr]


async def setup(bot: "dBot") -> None:
    await bot.add_cog(OnMessage(bot))
