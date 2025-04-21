import json
import re
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from statics.consts import PING_DATA

if TYPE_CHECKING:
    from dBot import dBot


class OnMessage(commands.Cog):

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    # @commands.Cog.listener("on_message")
    # async def bonusBot(self, message: discord.Message) -> None:
    #     if message.author.bot:
    #         return

    #     if message.content.startswith(("h!", "H!")) and message.channel.id in (
    #         401412343629742090,
    #         936397358852358164,
    #         936395886186098708,
    #         931718347190591498,
    #         953812391089537064,
    #     ):
    #         await message.reply("bonusBot was shut down on <t:1742765700:f>.")

    @commands.Cog.listener("on_message")
    async def bonusBot_info(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        if (
            message.content.lower() == "h!info wakeone"
            and message.channel.id == 401412343629742090
        ):
            await message.reply("Use dBot's `/info` instead.")

    @commands.Cog.listener("on_message")
    async def word_ping(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot:
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
                if user is None:
                    continue

                self.bot.pings[guild_id][word][user_id]["count"] += 1
                with open(PING_DATA, "w") as f:
                    json.dump(self.bot.pings, f, indent=4)

                embed = discord.Embed(
                    description=(
                        f"`{message.author.name}` mentioned `{word}` in "
                        f"<#{message.channel.id}> on "
                        f"<t:{int(message.created_at.timestamp())}:f>\n\n"
                        f"{message.content}"
                    ),
                    color=message.author.color,
                )
                embed.set_author(
                    name=f"Word Ping in {message.guild.name}",
                    url=message.jump_url,
                    icon_url=message.guild.icon.url if message.guild.icon else None,
                )
                embed.set_thumbnail(url=message.author.display_avatar.url)

                await user.send(embed=embed)


async def setup(bot: "dBot") -> None:
    await bot.add_cog(OnMessage(bot))
