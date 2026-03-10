import logging
from datetime import datetime, time
from typing import TYPE_CHECKING

from discord.ext import commands, tasks

from statics.consts import GAMES

if TYPE_CHECKING:
    from dBot import dBot
    from helpers.google_sheets import GoogleSheets


class SpreadsheetSync(commands.Cog):
    LOGGER = logging.getLogger(__name__.rpartition(".")[0])

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await self.spreadsheet_sync()
        self.spreadsheet_sync.start()

    async def cog_unload(self) -> None:
        self.spreadsheet_sync.cancel()
        self.bot.info_by_name.clear()
        self.bot.info_by_id.clear()

    @tasks.loop(time=[time(hour=h, minute=10) for h in range(24)])
    async def spreadsheet_sync(self) -> None:
        for game in GAMES:
            await self.get_spreadsheet_data(game)

    async def get_spreadsheet_data(self, game: str) -> None:
        game_details = GAMES[game]
        self.LOGGER.info("Downloading spreadsheet data: %s...", game_details["name"])
        cog: "GoogleSheets" = self.bot.get_cog(
            "GoogleSheets"
        )  # type: ignore[assignment]
        results = await cog.batch_get_sheet_data(
            game_details["spreadsheet"]["id"], game_details["spreadsheet"]["ranges"]
        )

        info_columns = game_details["spreadsheet"]["columns"][0]
        artist_name_index = info_columns.index("artist_name")
        song_name_index = info_columns.index("song_name")
        song_id_index = info_columns.index("song_id")

        info_by_name: dict[str, dict[str, list[str]]] = {}
        info_by_id: dict[str, list[str]] = {}
        for row in results[0]:
            if not row or (
                "album_name" in info_columns
                and not row[info_columns.index("album_name")]
            ):
                continue
            info_by_name.setdefault(row[artist_name_index], {})[
                row[song_name_index]
            ] = row
            info_by_id[row[song_id_index]] = row

        self.bot.info_by_name[game] = info_by_name
        self.bot.info_by_id[game] = info_by_id

        if "bonus_amount" not in game_details["spreadsheet"]["columns"][-1] or {
            "lastVersion"
        } <= set(game_details):
            return

        bonus_columns = game_details["spreadsheet"]["columns"][-1]
        artist_name_index = bonus_columns.index("artist_name")
        bonus_start_index = bonus_columns.index("bonus_start")
        bonus_end_index = bonus_columns.index("bonus_end")
        bonus_amount_index = bonus_columns.index("bonus_amount")
        date_format = game_details["dateFormat"]
        timezone = game_details["timezone"]

        bonus: dict[str, list[list]] = {}
        for row in results[-1]:
            if not row:
                continue
            new_row: list = row
            new_row[bonus_start_index] = datetime.strptime(
                row[bonus_start_index], date_format
            ).replace(tzinfo=timezone)
            new_row[bonus_end_index] = datetime.strptime(
                row[bonus_end_index], date_format
            ).replace(tzinfo=timezone)
            new_row[bonus_amount_index] = int(row[bonus_amount_index].replace("%", ""))
            bonus.setdefault(new_row[artist_name_index], []).append(new_row)

        self.bot.bonus[game] = bonus


async def setup(bot: "dBot") -> None:
    await bot.add_cog(SpreadsheetSync(bot))
