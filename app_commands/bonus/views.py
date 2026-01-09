from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import discord

from app_commands.bonus.commons import bonus_top_embeds

from .embeds import BonusListEmbed, BonusMaxEmbed
from .types import BonusDict

if TYPE_CHECKING:
    from dBot import dBot


class BonusListView(discord.ui.View):
    def __init__(
        self,
        message: discord.Message,
        game: str,
        artist_name: str | None,
        first_date: datetime,
        current_date: datetime,
        last_date: datetime,
        bonuses: list[BonusDict],
        user: discord.User | discord.Member,
        icon: str | Path | None,
        current_page: int,
        max_page: int,
    ) -> None:
        self.message = message
        self.game = game
        self.artist_name = artist_name
        self.bonuses = bonuses
        self.first_date = first_date
        self.current_date = current_date
        self.last_date = last_date
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
            embed=BonusListEmbed(
                self.game,
                self.artist_name,
                self.bonuses,
                self.first_date,
                self.current_date,
                self.last_date,
                self.icon,
                self.current_page,
                self.max_page,
            ),
            view=self,
        )

    @discord.ui.button(label="Previous Page", style=discord.ButtonStyle.primary)
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

    @discord.ui.button(label="Next Page", style=discord.ButtonStyle.success)
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


class BonusTopView(discord.ui.View):
    def __init__(
        self,
        message: discord.Message,
        game: str,
        current_date: datetime,
        last_date: datetime,
        all_bonuses: dict[str, list[BonusDict]],
        highest_bonuses: dict[str, list[BonusDict]],
        pages: list[discord.Embed],
        highest_scores: dict,
        total_score: int,
        user: discord.User | discord.Member,
        icon: str | Path | None,
    ) -> None:
        self.message = message
        self.game = game
        self.last_date = last_date
        self.current_date = current_date
        self.all_bonuses = all_bonuses
        self.highest_bonuses = highest_bonuses
        self.bonuses = self.highest_bonuses
        self.pages = pages
        self.highest_scores = highest_scores
        self.total_score = total_score
        self.user = user
        self.icon = icon
        self.current_page = 1
        self.max_page = len(self.pages)
        super().__init__()

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await self.message.edit(view=self)

    async def update_message(self, itr: discord.Interaction) -> None:
        await itr.followup.edit_message(
            message_id=self.message.id,
            embed=self.pages[self.current_page - 1],
            view=self,
        )

    @discord.ui.button(label="Previous Page", style=discord.ButtonStyle.primary, row=0)
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

    @discord.ui.button(label="Next Page", style=discord.ButtonStyle.success, row=0)
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

    @discord.ui.button(
        label="Highest Bonuses Only",
        style=discord.ButtonStyle.secondary,
        row=1,
        disabled=True,
    )
    async def show_highest(
        self, itr: discord.Interaction["dBot"], button: discord.ui.Button
    ) -> None:
        await itr.response.defer()
        if itr.user.id != self.user.id:
            await itr.followup.send(
                "You are not the original requester.", ephemeral=True
            )
            return

        self.pages = bonus_top_embeds(
            self.game,
            self.highest_bonuses,
            self.current_date,
            self.last_date,
            self.icon,
        )
        self.max_page = len(self.pages)
        self.current_page = 1

        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = False
        button.disabled = True
        await self.update_message(itr)

    @discord.ui.button(label="All Bonuses", style=discord.ButtonStyle.secondary, row=1)
    async def show_all(
        self, itr: discord.Interaction["dBot"], button: discord.ui.Button
    ) -> None:
        await itr.response.defer()
        if itr.user.id != self.user.id:
            await itr.followup.send(
                "You are not the original requester.", ephemeral=True
            )
            return

        self.pages = bonus_top_embeds(
            self.game,
            self.all_bonuses,
            self.current_date,
            self.last_date,
            self.icon,
        )
        self.max_page = len(self.pages)
        self.current_page = 1

        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = False
        button.disabled = True
        await self.update_message(itr)

    @discord.ui.button(
        label="Max Weekly Score", style=discord.ButtonStyle.secondary, row=1
    )
    async def show_score(
        self, itr: discord.Interaction["dBot"], button: discord.ui.Button
    ) -> None:
        await itr.response.defer()
        if itr.user.id != self.user.id:
            await itr.followup.send(
                "You are not the original requester.", ephemeral=True
            )
            return

        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if not child.row:
                    child.disabled = True
                else:
                    child.disabled = False
        button.disabled = True
        await itr.followup.edit_message(
            message_id=self.message.id,
            embed=BonusMaxEmbed(
                self.game,
                self.highest_scores,
                self.total_score,
                self.icon,
            ),
            view=self,
        )
