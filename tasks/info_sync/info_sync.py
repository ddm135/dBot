import logging
from datetime import time
from typing import TYPE_CHECKING

from discord.ext import commands, tasks

from statics.consts import GAMES

if TYPE_CHECKING:
    from dBot import dBot
    from helpers.google_sheets import GoogleSheets
    from statics.types import GameDetails


class InfoSync(commands.Cog):
    LOGGER = logging.getLogger(__name__.rpartition(".")[0])

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await self.info_sync()
        self.info_sync.start()

    async def cog_unload(self) -> None:
        self.info_sync.cancel()
        self.bot.info_by_name.clear()
        self.bot.info_by_id.clear()

    @tasks.loop(time=[time(hour=h, minute=15) for h in range(24)])
    async def info_sync(self) -> None:
        for game, game_details in GAMES.items():
            await self.get_info_data(game, game_details)

    async def get_info_data(self, game: str, game_details: "GameDetails") -> None:
        self.LOGGER.info("Downloading info data: %s...", game_details["name"])
        if not (info_details := game_details.get("info")):
            return

        cog: "GoogleSheets" = self.bot.get_cog(
            "GoogleSheets"
        )  # type: ignore[assignment]
        info = await cog.get_sheet_data(
            info_details["spreadsheetId"], info_details["range"]
        )

        info_columns = info_details["columns"]
        artist_name_index = info_columns.index("artist_name")
        song_name_index = info_columns.index("song_name")
        song_id_index = info_columns.index("song_id")
        duration_index = info_columns.index("duration")

        info_by_name: dict[str, dict[str, list[str]]] = {}
        info_by_id: dict[str, list[str]] = {}
        for row in info:
            if len(row) < len(info_columns):
                continue

            row[duration_index] = (
                row[duration_index]
                if ":" in row[duration_index]
                else f"{int(row[duration_index]) // 60}:"
                f"{int(row[duration_index]) % 60:02d}"
            )

            info_by_name.setdefault(row[artist_name_index], {})[
                row[song_name_index]
            ] = row
            info_by_id[row[song_id_index]] = row

        self.bot.info_by_name[game] = info_by_name
        self.bot.info_by_id[game] = info_by_id


async def setup(bot: "dBot") -> None:
    await bot.add_cog(InfoSync(bot))
