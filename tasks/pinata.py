import logging
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
        self.message: discord.Message
        super().__init__(**kwargs)

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        await self.message.edit(view=self)
        await super().on_timeout()

    @discord.ui.button(label="Join", style=discord.ButtonStyle.success)
    async def join_pinata(
        self, itr: discord.Interaction["dBot"], button: discord.ui.Button
    ) -> None:
        await itr.response.defer()
        if itr.user in self.joined:
            return
        self.joined.append(itr.user)
        await self.message.edit(embed=generate_embed([], self.joined))

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.danger)
    async def leave_pinata(
        self, itr: discord.Interaction["dBot"], button: discord.ui.Button
    ) -> None:
        await itr.response.defer()
        if itr.user not in self.joined:
            return
        self.joined.remove(itr.user)
        await self.message.edit(embed=generate_embed([], self.joined))


class Pinata(commands.Cog):
    LOGGER = logging.getLogger(__name__)

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    # async def cog_load(self) -> None:
    #     self.pinata.start()
    #     await super().cog_load()

    # async def cog_unload(self) -> None:
    #     self.pinata.cancel()
    #     await super().cog_unload()

    @tasks.loop(time=[time(hour=h, minute=m) for h in range(24) for m in range(60)])
    async def pinata(self) -> None:
        pinata_view = PinataView(timeout=30)
        message = await self.bot.get_channel(
            PINATA_TEST_CHANNEL,
        ).send(  # type: ignore[union-attr]
            embed=generate_embed([], []),
            view=pinata_view,
        )
        pinata_view.message = message
        await pinata_view.wait()
        self.LOGGER.info(pinata_view.joined)

    @pinata.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()


def generate_embed(
    rewards: list, attendees: list[discord.User | discord.Member]
) -> discord.Embed:
    description = (
        "Inside this piñata:\n**Absolutely nothing**\n\n**Party Attendees**\n"
    )
    for index, attendee in enumerate(attendees, start=1):
        description += f"{index}. {attendee.mention}\n"

    embed = discord.Embed(
        title="Piñata Drop",
        description=description,
    )
    return embed


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Pinata(bot))
