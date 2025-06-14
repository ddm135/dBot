import logging
from datetime import datetime, time
from typing import TYPE_CHECKING, Any

from discord.ext import commands, tasks

from statics.consts import GAMES, TIMEZONES
from statics.helpers import get_sheet_data

if TYPE_CHECKING:
    from dBot import dBot
    from statics.types import GameDetails


class BonusSync(commands.Cog):
    LOGGER = logging.getLogger(__name__)

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await self.bonus_sync()
        self.bonus_sync.start()

    async def cog_unload(self) -> None:
        self.bot.bonus_data_ready = False
        self.bonus_sync.cancel()
        self.bot.bonus_data.clear()

    @tasks.loop(time=time(hour=10, tzinfo=TIMEZONES["KST"]))
    async def bonus_sync(self) -> None:
        if self.bot.bonus_data_ready and datetime.now().weekday() != 0:
            return

        self.bot.bonus_data_ready = False
        self.LOGGER.info("Downloading bonus data...")

        for game, game_details in GAMES.items():
            await self.get_bonus_data(game, game_details)

        self.bot.bonus_data_ready = True

    async def get_bonus_data(self, game: str, game_details: "GameDetails") -> None:
        self.bot.bonus_data[game].clear()

        if not game_details["bonusSpreadsheet"]:
            return

        bonus = get_sheet_data(
            game_details["bonusSpreadsheet"],
            game_details["bonusRange"],
            "KR" if game_details["timezone"] == TIMEZONES["KST"] else None,
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
            row: list[Any] = raw_row
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

    @bonus_sync.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: "dBot") -> None:
    await bot.add_cog(BonusSync(bot))
