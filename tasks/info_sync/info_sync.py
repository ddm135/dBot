# mypy: disable-error-code="union-attr"
# pyright: reportAttributeAccessIssue=false, reportOptionalMemberAccess=false

import logging
from datetime import time
from typing import TYPE_CHECKING

from discord.ext import commands, tasks

from statics.consts import GAMES, TIMEZONES

if TYPE_CHECKING:
    from dBot import dBot
    from statics.types import GameDetails


class InfoSync(commands.Cog):
    LOGGER = logging.getLogger(__name__.rpartition(".")[0])

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await self.info_sync()
        self.info_sync.start()

    async def cog_unload(self) -> None:
        self.bot.info_ready = False
        self.info_sync.cancel()
        self.bot.info_by_name.clear()
        self.bot.info_by_id.clear()

    @tasks.loop(time=[time(hour=h, minute=20) for h in range(24)])
    async def info_sync(self) -> None:
        self.bot.info_ready = False
        for game, game_details in GAMES.items():
            await self.get_info_data(game, game_details)
        self.bot.info_ready = True

    async def get_info_data(self, game: str, game_details: "GameDetails") -> None:
        self.LOGGER.info("Downloading info data: %s...", game_details["name"])
        self.bot.info_by_name[game].clear()
        self.bot.info_by_id[game].clear()
        if not game_details["infoSpreadsheet"]:
            return

        cog = self.bot.get_cog("GoogleSheets")
        info = await cog.get_sheet_data(  # type: ignore[union-attr]
            game_details["infoSpreadsheet"],
            game_details["infoRange"],
            "kr" if game_details["timezone"] == TIMEZONES["KST"] else None,
        )

        info_columns = game_details["infoColumns"]
        artist_name_index = info_columns.index("artist_name")
        song_name_index = info_columns.index("song_name")
        song_id_index = info_columns.index("song_id")
        duration_index = info_columns.index("duration")

        for row in info:
            if not row or len(row) < len(info_columns):
                continue

            row[duration_index] = (
                row[duration_index]
                if ":" in row[duration_index]
                else f"{int(row[duration_index]) // 60}:"
                f"{int(row[duration_index]) % 60:02d}"
            )

            self.bot.info_by_name[game][row[artist_name_index]][
                row[song_name_index]
            ] = row
            self.bot.info_by_id[game][row[song_id_index]] = row


async def setup(bot: "dBot") -> None:
    await bot.add_cog(InfoSync(bot))
