# mypy: disable-error-code="union-attr"
# pyright: reportAttributeAccessIssue=false, reportOptionalMemberAccess=false

import gzip
import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING

import aiohttp
from discord.ext import commands

from statics.consts import GAMES, TIMEZONES

if TYPE_CHECKING:
    from dBot import dBot
    from statics.types import GameDetails


class InfoSync(commands.Cog):
    LOGGER = logging.getLogger(__name__)

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await self.info_sync()

    async def cog_unload(self) -> None:
        self.bot.info_data_ready = False
        self.bot.info_ajs.clear()
        self.bot.info_msd.clear()
        self.bot.info_url.clear()
        self.bot.info_by_name.clear()
        self.bot.info_by_id.clear()

    async def info_sync(self) -> None:
        if self.bot.info_data_ready and datetime.now().weekday():
            return

        self.bot.info_data_ready = False
        for game, game_details in GAMES.items():
            await self.get_info_data(game, game_details)
        self.bot.info_data_ready = True

    async def get_info_data(self, game: str, game_details: "GameDetails") -> None:
        self.LOGGER.info("Downloading info data: %s...", game_details["name"])
        if game_details["api"]:
            cog = self.bot.get_cog("SuperStar")
            ajs = await cog.get_a_json(game_details["api"])

            if ajs["code"] == 1000:
                self.bot.info_ajs[game].clear()
                self.bot.info_ajs[game] = ajs
            else:
                self.LOGGER.info(
                    "%s server is unavailable. Skipping...", game_details["name"]
                )
                ajs = self.bot.info_ajs[game]

            if ajs:
                self.bot.info_msd[game].clear()
                self.bot.info_msd[game] = await cog.get_data(
                    ajs["result"]["context"]["MusicData"]["file"]
                )
                if game_details["legacyUrlScheme"]:
                    self.bot.info_url[game].clear()
                    self.bot.info_url[game] = await cog.get_data(
                        ajs["result"]["context"]["URLs"]["file"]
                    )

        self.bot.info_by_name[game].clear()
        self.bot.info_by_id[game].clear()
        if not game_details["infoSpreadsheet"]:
            return

        cog = self.bot.get_cog("GoogleSheets")
        info = cog.get_sheet_data(  # type: ignore[union-attr]
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
