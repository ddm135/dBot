import math
from pathlib import Path
from typing import TYPE_CHECKING

import discord

from .commons import STEP
from .embeds import InfoEmbed

if TYPE_CHECKING:
    from dBot import dBot


class InfoView(discord.ui.View):
    def __init__(
        self,
        message_id: discord.Message,
        game: str,
        artist_name: str | None,
        songs: list[list[str]],
        info: dict[str, dict[str, dict[str, str]]],
        user: discord.User | discord.Member,
        icon: str | Path | None,
    ) -> None:
        self.message = message_id
        self.game = game
        self.artist_name = artist_name
        self.songs = songs
        self.info = info
        self.user = user
        self.icon = icon
        self.current = 1
        self.max = math.ceil(len(songs) / STEP) or 1
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
                self.game,
                self.artist_name,
                self.songs,
                self.info,
                self.icon,
                self.current,
                self.max,
            ),
            view=self,
        )

    @discord.ui.button(label="Previous Page", style=discord.ButtonStyle.secondary)
    async def previous_page(
        self, itr: discord.Interaction["dBot"], _: discord.ui.Button
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
        self, itr: discord.Interaction["dBot"], _: discord.ui.Button
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
