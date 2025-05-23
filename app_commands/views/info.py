import math
from typing import TYPE_CHECKING

import discord

from app_commands.commons.info import STEP
from app_commands.embeds.info import InfoEmbed

if TYPE_CHECKING:
    from dBot import dBot
    from statics.types import GameDetails


class InfoView(discord.ui.View):
    def __init__(
        self,
        message_id: discord.Message,
        game_details: "GameDetails",
        artist: str | None,
        songs: list[list[str]],
        user: discord.User | discord.Member,
    ) -> None:
        self.message = message_id
        self.game_details = game_details
        self.artist = artist
        self.songs = songs
        self.current = 1
        self.max = math.ceil(len(songs) / STEP) or 1
        self.user = user
        super().__init__()

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await self.message.edit(view=self)

    async def update_message(self, itr: discord.Interaction) -> None:
        await itr.followup.edit_message(
            message_id=self.message.id,
            embed=InfoEmbed(
                self.game_details,
                self.artist,
                self.songs,
                self.current,
                self.max,
            ),
            view=self,
        )

    @discord.ui.button(label="Previous Page", style=discord.ButtonStyle.secondary)
    async def previous_page(
        self, itr: discord.Interaction["dBot"], button: discord.ui.Button
    ) -> None:
        await itr.response.defer()
        if itr.user.id != self.user.id:
            return await itr.followup.send(
                "You are not the original requester.", ephemeral=True
            )

        self.current -= 1
        if self.current < 1:
            self.current = self.max
        await self.update_message(itr)

    @discord.ui.button(label="Next Page", style=discord.ButtonStyle.primary)
    async def next_page(
        self, itr: discord.Interaction["dBot"], button: discord.ui.Button
    ) -> None:
        await itr.response.defer()
        if itr.user.id != self.user.id:
            return await itr.followup.send(
                "You are not the original requester.", ephemeral=True
            )

        self.current += 1
        if self.current > self.max:
            self.current = 1
        await self.update_message(itr)
