from datetime import datetime
from typing import TYPE_CHECKING

import discord

from app_commands.commons.bonus import STEP
from statics.consts import BONUS_OFFSET

if TYPE_CHECKING:
    from statics.types import GameDetails


class BonusPingsEmbed(discord.Embed):
    ...


class BonusesEmbed(discord.Embed):
    def __init__(
        self,
        game_details: "GameDetails",
        bonuses: list[dict],
        first_date: datetime,
        last_date: datetime,
        current_date: datetime,
        current_page: int,
        max_page: int,
    ) -> None:
        end = current_page * STEP
        start = end - STEP
        filtered_bonuses = bonuses[start:end]

        super().__init__(
            title=(
                f"{game_details["name"]} {current_date.strftime("%G-W%V")} Bonuses "
                f"({first_date.strftime("%B %d")} - {last_date.strftime("%B %d")})"
            ).replace(" 0", " "),
            description="None" if not filtered_bonuses else None,
            color=game_details["color"],
        )
        self.set_footer(text=f"Page {current_page}/{max_page}")

        for bonus in filtered_bonuses:
            self.add_field(
                name=(
                    f"{("~~" if bonus["bonus_end"] < current_date
                        else "" if bonus["bonus_start"] > current_date
                        else ":white_check_mark: ")}"
                    f"**{bonus["artist"]}**"
                    f"{(f" {bonus["members"]}"
                        if bonus["members"]
                        and bonus["artist"] != bonus["members"]
                        else "")}: "
                    f"{(bonus["song"] if bonus["song"]
                        else "All Songs :birthday:")}"
                    f"{("" if not bonus["song"]
                        else " :cd:" if bonus["bonus_amount"] == 3
                        else " :birthday: :dvd:")}"
                    f"{"~~" if bonus["bonus_end"] < current_date else ""}"
                ),
                value=(
                    f"{"~~" if bonus["bonus_end"] < current_date else ""}"
                    f"{bonus["bonus_amount"]}% | "
                    f"{bonus["bonus_start"].strftime("%B %d").replace(" 0", " ")} -"
                    f" {bonus["bonus_end"].strftime("%B %d").replace(" 0", " ")} | "
                    f"{("Expired" if bonus["bonus_end"] < current_date
                        else f"Available <t:{int(bonus["bonus_start"].timestamp())}:R>"
                        if bonus["bonus_start"] > current_date
                        else f"Ends <t:"
                        f"{int((bonus["bonus_end"] + BONUS_OFFSET).timestamp())}:R>")}"
                    f"{" :bangbang:" if bonus["bonus_start"] == last_date else ""}"
                    f"{"~~" if bonus["bonus_end"] < current_date else ""}"
                ),
                inline=False,
            )
