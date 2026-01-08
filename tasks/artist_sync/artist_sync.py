# mypy: disable-error-code="assignment"
# pyright: reportAssignmentType=false

import logging
from datetime import time
from typing import TYPE_CHECKING

from discord.ext import commands, tasks

from statics.consts import GAMES, ArtistColumns

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
        emblem_index = artist_columns.index("emblem")
        max_score_index = (
            artist_columns.index("max_score")
            if artist_columns == ArtistColumns.STANDARD.value
            else None
        )

        data: dict[str, "ArtistDetails"] = {}
        ss_cog: "SuperStar" = self.bot.get_cog("SuperStar")
        for row in artist:
            artist_name = row[artist_name_index]
            emblem_value = row[emblem_index]
            max_score = int(row[max_score_index]) if max_score_index else 0

            try:
                emblem_final = (
                    await ss_cog.get_attributes(
                        game, "GroupData", int(emblem_value), {"emblemImage": True}
                    )
                )["emblemImage"]
            except ValueError:
                emblem_final = emblem_value
            data[artist_name] = {"emblem": emblem_final, "score": max_score}

        self.bot.artist[game] = data


async def setup(bot: "dBot") -> None:
    await bot.add_cog(ArtistSync(bot))
