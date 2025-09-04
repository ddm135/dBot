import logging
from datetime import time
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

from statics.consts import GAMES, TIMEZONES

if TYPE_CHECKING:
    from dBot import dBot
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
        self.bot.info_by_name.clear()
        self.bot.info_by_id.clear()

    @tasks.loop(time=[time(hour=h, minute=25) for h in range(24)])
    async def emblem_sync(self) -> None:
        for game, game_details in GAMES.items():
            await self.get_emblem_data(game, game_details)

    async def get_emblem_data(self, game: str, game_details: "GameDetails") -> None:
        self.LOGGER.info("Downloading emblem data: %s...", game_details["name"])
        if not (emblem_details := game_details.get("emblem")):
            return

        cog = self.bot.get_cog("GoogleSheets")
        emblem = await cog.get_sheet_data(  # type: ignore[union-attr]
            emblem_details["spreadsheetId"],
            emblem_details["range"],
            "kr" if game_details["timezone"] == TIMEZONES["KST"] else None,
        )

        emblem_columns = emblem_details["columns"]
        artist_name_index = emblem_columns.index("artist_name")
        emblem_index = emblem_columns.index("emblem")

        data: dict[str, str | discord.File | None] = {}
        cog = self.bot.get_cog("SuperStar")
        for row in emblem:
            artist_name = row[artist_name_index]
            emblem_value = row[emblem_index]
            try:
                emblem_value = int(emblem_value)
                emblem_final = (
                    await cog.get_attributes(  # type: ignore[union-attr]
                        game, "grd", emblem_value, {"emblemImage": True}
                    )
                )["emblemImage"]
            except Exception as e:
                self.LOGGER.exception(e)
                emblem_final = str(emblem_value)
            data[artist_name] = emblem_final

        self.bot.emblem[game] = data


async def setup(bot: "dBot") -> None:
    await bot.add_cog(EmblemSync(bot))
