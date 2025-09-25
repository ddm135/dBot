import logging
from datetime import datetime, time
from typing import TYPE_CHECKING

from discord.ext import commands, tasks

from statics.consts import GAMES

if TYPE_CHECKING:
    from dBot import dBot
    from helpers.google_sheets import GoogleSheets
    from statics.types import GameDetails


class BonusSync(commands.Cog):
    LOGGER = logging.getLogger(__name__.rpartition(".")[0])

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await self.bonus_sync()
        self.bonus_sync.start()

    async def cog_unload(self) -> None:
        self.bonus_sync.cancel()
        self.bot.bonus.clear()

    @tasks.loop(time=[time(hour=h, minute=15) for h in range(24)])
    async def bonus_sync(self) -> None:
        for game, game_details in GAMES.items():
            await self.get_bonus_data(game, game_details)

    async def get_bonus_data(self, game: str, game_details: "GameDetails") -> None:
        if not (bonus_details := game_details.get("bonus")):
            return
        self.LOGGER.info("Downloading bonus data: %s...", game_details["name"])

        cog: "GoogleSheets" = self.bot.get_cog(
            "GoogleSheets"
        )  # type: ignore[assignment]
        bonus = await cog.get_sheet_data(
            bonus_details["spreadsheetId"], bonus_details["range"]
        )

        bonus_columns = bonus_details["columns"]
        artist_name_index = bonus_columns.index("artist_name")
        bonus_start_index = bonus_columns.index("bonus_start")
        bonus_end_index = bonus_columns.index("bonus_end")
        bonus_amount_index = bonus_columns.index("bonus_amount")
        duration_index = bonus_columns.index("duration")
        date_format = game_details["dateFormat"]
        timezone = game_details["timezone"]

        data: dict[str, list[list]] = {}
        for raw_row in bonus:
            if len(raw_row) < len(bonus_columns):
                continue

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
                    or "N/A" in raw_row[duration_index]
                    else f"{int(raw_row[duration_index]) // 60}:"
                    f"{int(raw_row[duration_index]) % 60:02d}"
                )
            )
            row[bonus_amount_index] = int(raw_row[bonus_amount_index].replace("%", ""))
            data.setdefault(row[artist_name_index], []).append(row)

        self.bot.bonus[game] = data


async def setup(bot: "dBot") -> None:
    await bot.add_cog(BonusSync(bot))
