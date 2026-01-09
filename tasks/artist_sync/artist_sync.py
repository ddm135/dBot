# mypy: disable-error-code="assignment"
# pyright: reportAssignmentType=false

import logging
from datetime import time
from typing import TYPE_CHECKING

from discord.ext import commands, tasks

from statics.consts import GAMES

if TYPE_CHECKING:
    from dBot import dBot
    from helpers.google_sheets import GoogleSheets
    from helpers.superstar import SuperStar
    from statics.types import ArtistDetails, GameDetails


class ArtistSync(commands.Cog):
    LOGGER = logging.getLogger(__name__.rpartition(".")[0])

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await self.artist_sync()
        self.artist_sync.start()

    async def cog_unload(self) -> None:
        self.artist_sync.cancel()
        self.bot.artist.clear()

    @tasks.loop(time=[time(hour=h, minute=25) for h in range(24)])
    async def artist_sync(self) -> None:
        for game, game_details in GAMES.items():
            await self.get_artist_data(game, game_details)

    async def get_artist_data(self, game: str, game_details: "GameDetails") -> None:
        self.LOGGER.info("Downloading artist data: %s...", game_details["name"])
        sheets_cog: "GoogleSheets" = self.bot.get_cog("GoogleSheets")
        artist_details = game_details["artist"]
        artist = await sheets_cog.get_sheet_data(
            artist_details["spreadsheetId"], artist_details["range"]
        )

        artist_columns = artist_details["columns"]
        artist_name_index = artist_columns.index("artist_name")
        artist_code_index = artist_columns.index("artist_code")
        member_count_index = artist_columns.index("member_count")

        data: dict[str, "ArtistDetails"] = {}
        ss_cog: "SuperStar" = self.bot.get_cog("SuperStar")
        for row in artist:
            artist_name = row[artist_name_index]
            artist_code = int(row[artist_code_index])
            member_count = int(row[member_count_index])
            max_score = (
                game_details["base_score"] + 15_000 * (member_count - 3)
                if "base_score" in game_details
                else 0
            )
            emblem = (
                await ss_cog.get_attributes(
                    game, "GroupData", artist_code, {"emblemImage": True}
                )
            )["emblemImage"]
            data[artist_name] = {
                "code": artist_code,
                "emblem": emblem,
                "count": member_count,
                "score": max_score,
            }

        self.bot.artist[game] = data


async def setup(bot: "dBot") -> None:
    await bot.add_cog(ArtistSync(bot))
