from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import discord

from statics.consts import BONUS_OFFSET

from .embeds import BonusListEmbed, BonusMaxEmbed, BonusTopEmbed
from .types import BonusDict

if TYPE_CHECKING:
    from dBot import dBot
    from statics.types import GameDetails


class BonusListView(discord.ui.View):
    def __init__(
        self,
        message: discord.Message,
        game_details: "GameDetails",
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
        self.game_details = game_details
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
                self.game_details,
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
        game_details: "GameDetails",
        current_date: datetime,
        last_date: datetime,
        all_bonuses: dict[str, list[BonusDict]],
        highest_bonuses: dict[str, list[BonusDict]],
        all_pages: dict,
        highest_pages: dict,
        highest_scores: dict,
        total_score: int,
        user: discord.User | discord.Member,
        icon: str | Path | None,
    ) -> None:
        self.message = message
        self.game_details = game_details
        self.last_date = last_date
        self.current_date = current_date
        self.all_bonuses = all_bonuses
        self.highest_bonuses = highest_bonuses
        self.bonuses = self.highest_bonuses
        self.all_pages = all_pages
        self.highest_pages = highest_pages
        self.pages = self.highest_pages
        self.highest_scores = highest_scores
        self.total_score = total_score
        self.user = user
        self.icon = icon
        self.current_page = 1
        self.max_page = max(self.pages)
        self.is_condensed = False
        self.condensed_pages: list[discord.Embed] = []
        super().__init__()

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await self.message.edit(view=self)

    async def update_message(self, itr: discord.Interaction) -> None:
        await itr.followup.edit_message(
            message_id=self.message.id,
            embed=(
                BonusTopEmbed(
                    self.game_details,
                    self.bonuses,
                    self.current_date,
                    self.last_date,
                    self.icon,
                    self.pages,
                    self.current_page,
                    self.max_page,
                )
                if not self.is_condensed
                else self.condensed_pages[self.current_page]
            ),
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
        label="Toggle Condensed Mode", style=discord.ButtonStyle.secondary, row=0
    )
    async def toggle_condensed(
        self, itr: discord.Interaction["dBot"], _: discord.ui.Button
    ) -> None:
        await itr.response.defer()
        if itr.user.id != self.user.id:
            await itr.followup.send(
                "You are not the original requester.", ephemeral=True
            )
            return

        self.is_condensed = not self.is_condensed
        self.condensed_pages = self.condensed(
            self.game_details,
            self.bonuses,
            self.current_date,
            self.last_date,
            self.icon,
        ) if self.is_condensed else []
        self.max_page = (
            max(self.pages) if self.is_condensed else len(self.condensed_pages)
        )
        self.current_page = 1
        await self.update_message(itr)

    @discord.ui.button(
        label="Highest Bonuses Only",
        style=discord.ButtonStyle.secondary,
        row=1,
        disabled=True,
    )
    async def show_highest(
        self, itr: discord.Interaction["dBot"], _: discord.ui.Button
    ) -> None:
        await itr.response.defer()
        if itr.user.id != self.user.id:
            await itr.followup.send(
                "You are not the original requester.", ephemeral=True
            )
            return

        self.bonuses = self.highest_bonuses
        self.pages = self.highest_pages
        self.max_page = (
            max(self.pages) if self.is_condensed else len(self.condensed_pages)
        )

        if self.is_condensed:
            self.condensed_pages = self.condensed(
                self.game_details,
                self.bonuses,
                self.current_date,
                self.last_date,
                self.icon,
            )
        else:
            active_page = self.pages[self.current_page]
            for page_number, page_details in self.pages.items():
                if page_details["artist"] == active_page["artist"]:
                    self.current_page = page_number
                    break

        await self.update_message(itr)

    @discord.ui.button(
        label="All Bonuses",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def show_all(
        self, itr: discord.Interaction["dBot"], _: discord.ui.Button
    ) -> None:
        await itr.response.defer()
        if itr.user.id != self.user.id:
            await itr.followup.send(
                "You are not the original requester.", ephemeral=True
            )
            return

        self.bonuses = self.all_bonuses
        self.pages = self.all_pages
        self.max_page = (
            max(self.pages) if self.is_condensed else len(self.condensed_pages)
        )

        if self.is_condensed:
            self.condensed_pages = self.condensed(
                self.game_details,
                self.bonuses,
                self.current_date,
                self.last_date,
                self.icon,
            )
        else:
            active_page = self.pages[self.current_page]
            for page_number, page_details in self.pages.items():
                if page_details["artist"] == active_page["artist"]:
                    self.current_page = page_number
                    break
        await self.update_message(itr)

    @discord.ui.button(
        label="Max Weekly Score",
        style=discord.ButtonStyle.secondary,
        row=1,
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
                self.game_details, self.highest_scores, self.total_score, self.icon
            ),
            view=self,
        )

    def condensed(
        self,
        game_details: "GameDetails",
        bonuses: dict[str, list[BonusDict]],
        current_date: datetime,
        last_date: datetime,
        icon: str | Path | None,
    ) -> list[discord.Embed]:
        embeds: list[discord.Embed] = []
        author = f"{game_details["name"]} - Top Bonuses"
        embeds.append(discord.Embed(color=game_details["color"]))
        embeds[-1].set_author(
            name=author,
            icon_url="attachment://icon.png" if isinstance(icon, Path) else icon,
        )
        embed_count = len(author)
        embed_field_count = 0

        for artist_name, _bonuses in bonuses.items():
            field_name = (
                artist_name.replace(r"*", r"\*")
                .replace(r"_", r"\_")
                .replace(r"`", r"\`")
            )
            field_value = ""
            field_name_count = len(field_name)
            field_value_count = 0

            for bonus in _bonuses:
                text = (
                    f"> **{"~~" if bonus["bonusEnd"] < current_date
                           else "" if bonus["bonusStart"] > current_date
                           else ":white_check_mark: "}"
                    f"{bonus["members"].replace(r"*", r"\*")
                        .replace(r"_", r"\_").replace(r"`", r"\`")
                        if bonus["members"]
                        and bonus["artist"] != bonus["members"]
                        else ""}"
                    f"{": " if not artist_name
                        or bonus["members"] and bonus["artist"] != bonus["members"]
                        else ""}"
                    f"{bonus["song"].replace(r"*", r"\*")
                        .replace(r"_", r"\_").replace(r"`", r"\`")
                        if bonus["song"]
                        else "All Songs :birthday:"}"
                    f"{"" if not bonus["song"]
                        else " :cd:" if bonus["bonusAmount"] == 3
                        else " :birthday: :dvd:"}"
                    f"{"~~" if bonus["bonusEnd"] < current_date else ""}**\n"
                    f"> {"~~" if bonus["bonusEnd"] < current_date else ""}"
                    f"{bonus["bonusAmount"]}% | "
                    f"{bonus["bonusStart"].strftime("%B %d").replace(" 0", " ")} - "
                    f"{bonus["bonusEnd"].strftime("%B %d").replace(" 0", " ")} | "
                    f"{f"{bonus["maxScore"]:,} | " if bonus["maxScore"] else ""}"
                    f"{"Expired" if bonus["bonusEnd"] < current_date
                        else f"Available <t:{int(bonus["bonusStart"].timestamp())}:R>"
                        if bonus["bonusStart"] > current_date
                        else f"Ends <t:"
                        f"{int((bonus["bonusEnd"] + BONUS_OFFSET).timestamp())}:R>"}"
                    f"{" :bangbang:" if bonus["bonusStart"] == last_date else ""}"
                    f"{"~~" if bonus["bonusEnd"] < current_date else ""}\n"
                )
                text_count = len(text)

                if (
                    embed_count + field_name_count + field_value_count + text_count
                    > 6000
                    or embed_field_count > 25
                ):
                    embeds.append(discord.Embed(color=game_details["color"]))
                    embed_count = 0
                    embed_field_count = 0
                if field_value_count + text_count > 1024:
                    embeds[-1].add_field(
                        name=field_name, value=field_value, inline=False
                    )
                    embed_count += field_name_count + field_value_count

                    field_name = ""
                    field_value = ""
                    field_name_count = 0
                    field_value_count = 0

                field_value += text
                field_value_count += text_count

            if (
                embed_count + field_name_count + field_value_count > 6000
                or embed_field_count > 25
            ):
                embeds.append(discord.Embed(color=game_details["color"]))
                embed_count = 0
                embed_field_count = 0

            embeds[-1].add_field(name=field_name, value=field_value, inline=False)
            embed_count += field_name_count + field_value_count

        page_count = len(embeds)
        for index, embed in enumerate(embeds, 1):
            embed.set_footer(text=f"Page {index}/{page_count}")

        return embeds
