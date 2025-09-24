import re
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from statics.consts import Data

from .embeds import WordPingEmbed

if TYPE_CHECKING:
    from dBot import dBot
    from tasks.data_sync import DataSync


class OnMessage(commands.Cog):
    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    @commands.Cog.listener("on_message")
    async def word_ping(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return

        guild_id = str(message.guild.id)
        for word in self.bot.word_pings[guild_id]:
            reg_exp = (
                rf"(?:(?:[\s!@#\$%\^&\*\(\)\-_=\+\[{{\]}}\\\\\|;:'\",<\.>\/\?])+|^)"
                rf"{re.escape(word)}"
                rf"(?:(?:[\s!@#\$%\^&\*\(\)\-_=\+\[{{\]}}\\\\\|;:'\",<\.>\/\?])+|$)"
            )
            if not re.search(reg_exp, message.content, flags=re.IGNORECASE):
                continue

            for user_id, user_ping_data in self.bot.word_pings[guild_id][word].items():
                user_id_int = int(user_id)
                if (
                    message.author.id == user_id_int
                    or not user_ping_data
                    or message.author.id in user_ping_data["users"]
                    or message.channel.id in user_ping_data["channels"]
                ):
                    continue

                try:
                    user = self.bot.get_user(user_id_int) or await self.bot.fetch_user(
                        user_id_int
                    )
                    await user.send(embed=WordPingEmbed(word, message))
                except (discord.NotFound, discord.Forbidden):
                    continue

                user_ping_data["count"] += 1
                cog: "DataSync" = self.bot.get_cog(
                    "DataSync"
                )  # type: ignore[assignment]
                cog.save_data(Data.WORD_PINGS)


async def setup(bot: "dBot") -> None:
    await bot.add_cog(OnMessage(bot))
