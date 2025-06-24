import logging
from datetime import datetime
from typing import TYPE_CHECKING

from discord.ext import commands

from statics.consts import GAMES, TIMEZONES

if TYPE_CHECKING:
    from dBot import dBot
    from statics.types import GameDetails


class BonusSync(commands.Cog):
    LOGGER = logging.getLogger(__name__.rpartition(".")[0])

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await self.bonus_sync()

    async def cog_unload(self) -> None:
        self.bot.bonus_data_ready = False
        self.bot.bonus_data.clear()

    async def bonus_sync(self) -> None:
        if self.bot.bonus_data_ready and datetime.now().weekday():
            return

        self.bot.bonus_data_ready = False
        for game, game_details in GAMES.items():
            await self.get_bonus_data(game, game_details)
        self.bot.bonus_data_ready = True

    async def get_bonus_data(self, game: str, game_details: "GameDetails") -> None:
        if not game_details["bonusSpreadsheet"]:
            return
        self.LOGGER.info("Downloading bonus data: %s...", game_details["name"])
        self.bot.bonus_data[game].clear()

        cog = self.bot.get_cog("GoogleSheets")
        bonus = await cog.get_sheet_data(  # type: ignore[union-attr]
            game_details["bonusSpreadsheet"],
            game_details["bonusRange"],
            "kr" if game_details["timezone"] == TIMEZONES["KST"] else None,
        )

        bonus_columns = game_details["bonusColumns"]
        artist_name_index = bonus_columns.index("artist_name")
        bonus_start_index = bonus_columns.index("bonus_start")
        bonus_end_index = bonus_columns.index("bonus_end")
        bonus_amount_index = bonus_columns.index("bonus_amount")
        duration_index = bonus_columns.index("duration")
        date_format = game_details["dateFormat"]
        timezone = game_details["timezone"]

        for raw_row in bonus:
            row: list = raw_row
            row[bonus_start_index] = datetime.strptime(
                raw_row[bonus_start_index], date_format
            ).replace(tzinfo=timezone)
            row[bonus_end_index] = datetime.strptime(
                raw_row[bonus_end_index], date_format
            ).replace(tzinfo=timezone)
            row[duration_index] = (
                ""
                if not raw_row[duration_index]
                else (
                    raw_row[duration_index]
                    if ":" in raw_row[duration_index]
                    else f"{int(raw_row[duration_index]) // 60}:"
                    f"{int(raw_row[duration_index]) % 60:02d}"
                )
            )
            row[bonus_amount_index] = int(raw_row[bonus_amount_index].replace("%", ""))
            self.bot.bonus_data[game][raw_row[artist_name_index]].append(row)


async def setup(bot: "dBot") -> None:
    await bot.add_cog(BonusSync(bot))
