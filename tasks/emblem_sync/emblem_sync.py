import logging
from datetime import time
from pathlib import Path
from typing import TYPE_CHECKING

from discord.ext import commands, tasks

from statics.consts import GAMES, TIMEZONES

if TYPE_CHECKING:
    from dBot import dBot
    from helpers.google_sheets import GoogleSheets
    from helpers.superstar import SuperStar
    from statics.types import GameDetails


class EmblemSync(commands.Cog):
    LOGGER = logging.getLogger(__name__.rpartition(".")[0])

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await self.emblem_sync()
        self.emblem_sync.start()

    async def cog_unload(self) -> None:
        self.emblem_sync.cancel()
        self.bot.emblem.clear()

    @tasks.loop(time=[time(hour=h, minute=25) for h in range(24)])
    async def emblem_sync(self) -> None:
        for game, game_details in GAMES.items():
            await self.get_emblem_data(game, game_details)

    async def get_emblem_data(self, game: str, game_details: "GameDetails") -> None:
        self.LOGGER.info("Downloading emblem data: %s...", game_details["name"])
        sheets_cog: "GoogleSheets" = self.bot.get_cog(
            "GoogleSheets"
        )  # type: ignore[assignment]
        emblem_details = game_details["emblem"]
        emblem = await sheets_cog.get_sheet_data(  # type: ignore[union-attr]
            emblem_details["spreadsheetId"],
            emblem_details["range"],
            "kr" if game_details["timezone"] == TIMEZONES["KST"] else None,
        )

        emblem_columns = emblem_details["columns"]
        artist_name_index = emblem_columns.index("artist_name")
        emblem_index = emblem_columns.index("emblem")

        data: dict[str, str | Path | None] = {}
        ss_cog: "SuperStar" = self.bot.get_cog("SuperStar")  # type: ignore[assignment]
        for row in emblem:
            artist_name = row[artist_name_index]
            emblem_value = row[emblem_index]
            try:
                emblem_final = (
                    await ss_cog.get_attributes(
                        game, "grd", int(emblem_value), {"emblemImage": True}
                    )
                )["emblemImage"]
            except ValueError:
                emblem_final = emblem_value
            data[artist_name] = emblem_final

        self.bot.emblem[game] = data


async def setup(bot: "dBot") -> None:
    await bot.add_cog(EmblemSync(bot))
