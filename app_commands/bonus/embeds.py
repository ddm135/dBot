# pyright: reportTypedDictNotRequiredAccess=false

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import discord

from statics.consts import BONUS_OFFSET, GAMES

from .commons import STEP
from .types import BonusDict

if TYPE_CHECKING:
    from statics.types import GameDetails


class BonusPingsEmbed(discord.Embed):
    def __init__(
        self,
        game: str,
        ping_data: list[list[str]],
        user_id: str,
        icon: str,
    ) -> None:
        game_details = GAMES[game]
        ping_columns = game_details["ping"]["columns"]
        artist_name_index = ping_columns.index("artist_name")
        users_index = ping_columns.index("users")
        description = ""

        for row in ping_data:
            _artist_name = row[artist_name_index]
            users = row[users_index].split(",")
            if "" in users:
                users.remove("")

            if user_id in users:
                description += f"- {_artist_name}\n"

        if not description:
            description = "None"
        else:
            description = description[:-1]

        super().__init__(
            description=description,
            color=game_details["color"],
        )
        self.set_author(name=game_details["name"], icon_url=icon)


class BonusesEmbed(discord.Embed):
    def __init__(
        self,
        game_details: "GameDetails",
        artist_name: str | None,
        bonuses: list[BonusDict],
        first_date: datetime,
        last_date: datetime,
        current_date: datetime,
        icon: str | Path | None,
        current_page: int,
        max_page: int,
    ) -> None:
        end = current_page * STEP
        start = end - STEP
        filtered_bonuses = bonuses[start:end]

        super().__init__(
            title=(
                f"{(artist_name.replace(r"*", r"\*").replace(r"_", r"\_")
                    .replace(r"`", r"\`")) if artist_name else "All Bonuses"} ("
                f"{first_date.strftime("%B %d").replace(" 0", " ")} - "
                f"{last_date.strftime("%B %d").replace(" 0", " ")})"
            ),
            description="None" if not filtered_bonuses else None,
            color=game_details["color"],
        )
        self.set_author(
            name=f"{game_details["name"]} - Bonus Info",
            icon_url="attachment://icon.png" if isinstance(icon, Path) else icon,
        )
        self.set_footer(text=f"Page {current_page}/{max_page}")

        for bonus in filtered_bonuses:
            self.add_field(
                name=(
                    f"{("~~" if bonus["bonusEnd"] < current_date
                        else "" if bonus["bonusStart"] > current_date
                        else ":white_check_mark: ")}"
                    f"{f"**{bonus["artist"]}**" if not artist_name else ""}"
                    f"{" " if not artist_name and bonus["members"] else ""}"
                    f"{(f"{bonus["members"]}"
                        if bonus["members"]
                        and bonus["artist"] != bonus["members"]
                        else "")}"
                    f"{(": " if not artist_name
                        or bonus["members"] and bonus["artist"] != bonus["members"]
                        else "")}"
                    f"{(bonus["song"] if bonus["song"]
                        else "All Songs :birthday:")}"
                    f"{("" if not bonus["song"]
                        else " :cd:" if bonus["bonusAmount"] == 3
                        else " :birthday: :dvd:")}"
                    f"{"~~" if bonus["bonusEnd"] < current_date else ""}"
                ),
                value=(
                    f"{"~~" if bonus["bonusEnd"] < current_date else ""}"
                    f"{bonus["bonusAmount"]}% | "
                    f"{bonus["bonusStart"].strftime("%B %d").replace(" 0", " ")} - "
                    f"{bonus["bonusEnd"].strftime("%B %d").replace(" 0", " ")} | "
                    f"{f"{bonus["maxScore"]:,} | " if bonus["maxScore"] else ""}"
                    f"{("Expired" if bonus["bonusEnd"] < current_date
                        else f"Available <t:{int(bonus["bonusStart"].timestamp())}:R>"
                        if bonus["bonusStart"] > current_date
                        else f"Ends <t:"
                        f"{int((bonus["bonusEnd"] + BONUS_OFFSET).timestamp())}:R>")}"
                    f"{" :bangbang:" if bonus["bonusStart"] == last_date else ""}"
                    f"{"~~" if bonus["bonusEnd"] < current_date else ""}"
                ),
                inline=False,
            )
