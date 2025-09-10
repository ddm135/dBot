from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import discord

from .embeds import BonusesEmbed
from .types import BonusDict

if TYPE_CHECKING:
    from dBot import dBot
    from statics.types import GameDetails


class BonusView(discord.ui.View):
    def __init__(
        self,
        message: discord.Message,
        game_details: "GameDetails",
        artist: str | None,
        first_date: datetime,
        last_date: datetime,
        current_date: datetime,
        bonuses: list[BonusDict],
        user: discord.User | discord.Member,
        icon: str | Path | None,
        current_page: int,
        max_page: int,
    ) -> None:
        self.message = message
        self.game_details = game_details
        self.artist = artist
        self.bonuses = bonuses
        self.first_date = first_date
        self.last_date = last_date
        self.current_date = current_date
        self.user = user
        self.icon = icon
        self.current_page = current_page
        self.max_page = max_page
        super().__init__()

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await self.message.edit(view=self)

    async def update_message(self, itr: discord.Interaction) -> None:
        await itr.followup.edit_message(
            message_id=self.message.id,
            embed=BonusesEmbed(
                self.game_details,
                self.artist,
                self.bonuses,
                self.first_date,
                self.last_date,
                self.current_date,
                self.icon,
                self.current_page,
                self.max_page,
            ),
            view=self,
        )

    @discord.ui.button(label="Previous Page", style=discord.ButtonStyle.secondary)
    async def previous_page(
        self, itr: discord.Interaction["dBot"], _: discord.ui.Button
    ) -> None:
        await itr.response.defer()
        if itr.user.id != self.user.id:
            await itr.followup.send(
                "You are not the original requester.", ephemeral=True
            )
            return

        self.current_page -= 1
        if self.current_page < 1:
            self.current_page = self.max_page
        await self.update_message(itr)

    @discord.ui.button(label="Next Page", style=discord.ButtonStyle.primary)
    async def next_page(
        self, itr: discord.Interaction["dBot"], _: discord.ui.Button
    ) -> None:
        await itr.response.defer()
        if itr.user.id != self.user.id:
            await itr.followup.send(
                "You are not the original requester.", ephemeral=True
            )
            return

        self.current_page += 1
        if self.current_page > self.max_page:
            self.current_page = 1
        await self.update_message(itr)
