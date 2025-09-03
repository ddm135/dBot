import base64
import binascii
import json
import logging
from datetime import time
from typing import TYPE_CHECKING

from discord.ext import commands, tasks

from statics.consts import GAMES, AssetScheme

if TYPE_CHECKING:
    from dBot import dBot
    from statics.types import GameDetails


class DalcomSync(commands.Cog):
    LOGGER = logging.getLogger(__name__.rpartition(".")[0])

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await self.dalcom_sync()
        self.dalcom_sync.start()

    async def cog_unload(self) -> None:
        self.dalcom_sync.cancel()
        self.bot.ajs.clear()
        self.bot.msd.clear()
        self.bot.grd.clear()
        self.bot.url.clear()

    @tasks.loop(time=[time(hour=h, minute=10) for h in range(24)])
    async def dalcom_sync(self) -> None:
        for game, game_details in GAMES.items():
            await self.get_dalcom_data(game, game_details)

    async def get_dalcom_data(self, game: str, game_details: "GameDetails") -> None:
        try:
            if not (basic_details := self.bot.basic.get(game)):
                return

            self.LOGGER.info("Downloading Dalcom data: %s...", game_details["name"])
            cog = self.bot.get_cog("SuperStar")
            ajs = await cog.get_a_json(basic_details)  # type: ignore[union-attr]

            if ajs["code"] == 1000:
                self.bot.ajs[game] = ajs
            else:
                self.LOGGER.info(
                    "%s server is unavailable. Skipping...", game_details["name"]
                )
                ajs = self.bot.ajs[game]

            if ajs:
                self.bot.msd[game] = await cog.get_data(  # type: ignore[union-attr]
                    ajs["result"]["context"]["MusicData"]["file"]
                )
                self.bot.grd[game] = await cog.get_data(  # type: ignore[union-attr]
                    ajs["result"]["context"]["GroupData"]["file"]
                )
                if game_details["assetScheme"] == AssetScheme.JSON_URL:
                    self.bot.url[game] = await cog.get_data(  # type: ignore[union-attr]
                        ajs["result"]["context"]["URLs"]["file"]
                    )
        except (json.JSONDecodeError, binascii.Error):
            return
        except Exception as e:
            self.LOGGER.exception(str(e))
            return


async def setup(bot: "dBot") -> None:
    await bot.add_cog(DalcomSync(bot))
