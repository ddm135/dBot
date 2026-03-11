import math
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import discord

from .commons import STEP
from .embeds import ArtistWorldRecordEmbed, SongWorldRecordEmbed

if TYPE_CHECKING:
    from dBot import dBot


class SongWorldRecordView(discord.ui.View):
    def __init__(
        self,
        message: discord.Message,
        game: str,
        artist_name: str,
        song_name: str,
        season_code: int,
        start_date: datetime,
        end_date: datetime,
        world_records: list[dict],
        last_updated: datetime | None,
        user: discord.User | discord.Member,
        icon: str | Path | None,
    ) -> None:
        self.message = message
        self.game = game
        self.artist_name = artist_name
        self.song_name = song_name
        self.season_code = season_code
        self.start_date = start_date
        self.end_date = end_date
        self.world_records = world_records
        self.last_updated = last_updated
        self.user = user
        self.icon = icon
        self.current_page = 1
        self.max_page = math.ceil(len(world_records) / STEP) or 1
        super().__init__()

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await self.message.edit(view=self)

    async def update_message(self, itr: discord.Interaction) -> None:
        await itr.followup.edit_message(
            message_id=self.message.id,
            embed=SongWorldRecordEmbed(
                self.game,
                self.artist_name,
                self.song_name,
                self.season_code,
                self.start_date,
                self.end_date,
                self.world_records,
                self.last_updated,
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
            return await itr.followup.send(
                "You are not the original requester.", ephemeral=True
            )

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
            return await itr.followup.send(
                "You are not the original requester.", ephemeral=True
            )

        self.current_page += 1
        if self.current_page > self.max_page:
            self.current_page = 1
        await self.update_message(itr)


class ArtistWorldRecordView(discord.ui.View):
    def __init__(
        self,
        message: discord.Message,
        game: str,
        artist_name: str,
        season_code: int,
        start_date: datetime,
        end_date: datetime,
        world_records: dict[str, dict | str],
        last_updated: datetime | None,
        user: discord.User | discord.Member,
        icon: str | Path | None,
    ) -> None:
        self.message = message
        self.game = game
        self.artist_name = artist_name
        self.season_code = season_code
        self.start_date = start_date
        self.end_date = end_date
        self.world_records = world_records
        self.last_updated = last_updated
        self.user = user
        self.icon = icon
        self.current_page = 1
        self.max_page = math.ceil(len(world_records) / STEP) or 1
        super().__init__()

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await self.message.edit(view=self)

    async def update_message(self, itr: discord.Interaction) -> None:
        await itr.followup.edit_message(
            message_id=self.message.id,
            embed=ArtistWorldRecordEmbed(
                self.game,
                self.artist_name,
                self.season_code,
                self.start_date,
                self.end_date,
                self.world_records,
                self.last_updated,
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
            return await itr.followup.send(
                "You are not the original requester.", ephemeral=True
            )

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
            return await itr.followup.send(
                "You are not the original requester.", ephemeral=True
            )

        self.current_page += 1
        if self.current_page > self.max_page:
            self.current_page = 1
        await self.update_message(itr)
