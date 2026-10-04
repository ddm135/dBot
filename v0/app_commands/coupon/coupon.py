import random
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from .commons import REG_EXP, USER_AGENTS

if TYPE_CHECKING:
    from dBot import dBot


class Coupon(commands.Cog):
    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    @app_commands.command()
    async def coupon(self, itr: discord.Interaction["dBot"], link: str) -> None:
        """Extract coupon code from AppsFlyer OneLink

        Parameters
        -----------
        link: :class:`str`
            Link obtained from the QR code
        """

        await itr.response.defer()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    link,
                    allow_redirects=False,
                    headers={"User-Agent": random.choice(USER_AGENTS)},
                ) as r:
                    if redirect := r.headers.get("Location"):
                        queries = parse_qs(
                            parse_qs(urlsplit(redirect).query)["referrer"][0]
                        )
                    else:
                        queries = parse_qs(
                            urlsplit(
                                REG_EXP.search(await r.text()).group(1)  # type: ignore
                            ).query
                        )
            code = queries["deep_link_sub1"][0]
            await itr.followup.send(code)
        except Exception as e:
            await itr.followup.send("Failed to extract coupon code.", ephemeral=True)
            print(e)


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Coupon(bot))
