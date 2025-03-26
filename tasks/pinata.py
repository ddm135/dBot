from datetime import time
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

from statics.consts import PINATA_TEST_CHANNEL

if TYPE_CHECKING:
    from dBot import dBot


class PinataView(discord.ui.View):
    def __init__(self, **kwargs) -> None:
        self.joined: list[discord.User | discord.Member] = []
        super().__init__(**kwargs)

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        await super().on_timeout()

    @discord.ui.button(label="Join", style=discord.ButtonStyle.success)
    async def join_pinata(
        self, itr: discord.Interaction["dBot"], button: discord.ui.Button
    ) -> None:
        await itr.response.defer()
        if itr.user in self.joined:
            return
        self.joined.append(itr.user)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.danger)
    async def leave_pinata(
        self, itr: discord.Interaction["dBot"], button: discord.ui.Button
    ) -> None:
        await itr.response.defer()
        if itr.user not in self.joined:
            return
        self.joined.remove(itr.user)


class Pinata(commands.Cog):
    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    @tasks.loop(time=[time(hour=h, minute=m) for h in range(24) for m in range(60)])
    async def pinata(self) -> None:
        pinata_view = PinataView(timeout=300)
        self.bot.get_channel(PINATA_TEST_CHANNEL).send(  # type: ignore[union-attr]
            view=pinata_view,
        )
        await pinata_view.wait()

    @pinata.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Pinata(bot))
