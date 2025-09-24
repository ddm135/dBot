import binascii
import json
import logging
from datetime import time
from pathlib import Path
from typing import TYPE_CHECKING

from discord.ext import commands, tasks

from statics.consts import GAMES, AssetScheme

if TYPE_CHECKING:
    from dBot import dBot
    from helpers.superstar import SuperStar
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

    @tasks.loop(time=[time(hour=h, minute=10) for h in range(24)])
    async def dalcom_sync(self) -> None:
        for game, game_details in GAMES.items():
            await self.get_dalcom_data(game, game_details)

    async def get_dalcom_data(self, game: str, game_details: "GameDetails") -> None:
        try:
            if not (basic_details := self.bot.basic.get(game)):
                return
            ajs_path = Path(f"data/dalcom/{game}/a.json")
            if ajs_path.exists():
                with open(ajs_path, "r", encoding="utf-8") as f:
                    stored_ajs = json.load(f)
            else:
                stored_ajs = None

            self.LOGGER.info("Downloading Dalcom data: %s...", game_details["name"])
            cog: "SuperStar" = self.bot.get_cog("SuperStar")  # type: ignore[assignment]
            ajs = await cog.get_a_json(basic_details)
            refresh = True

            if ajs["code"] == 1000:
                if (
                    stored_ajs
                    and ajs["result"]["version"] == stored_ajs["result"]["version"]
                ):
                    refresh = False
                else:
                    ajs_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(ajs_path, "w", encoding="utf-8") as f:
                        json.dump(ajs, f, indent=4)
            else:
                ajs = stored_ajs
                refresh = False

            data_files = [
                "GroupData",
                "LocaleData",
                "MusicData",
                "ThemeData",
                "ThemeTypeData",
            ]
            if game_details["assetScheme"] == AssetScheme.JSON_URL:
                data_files.append("URLs")
            if ajs:
                for data_file in data_files:
                    data_path = Path(f"data/dalcom/{game}/{data_file}.json")
                    if (
                        not stored_ajs
                        or ajs["result"]["context"][data_file]["version"]
                        != stored_ajs["result"]["context"][data_file]["version"]
                        or refresh
                        or not data_path.exists()
                    ):
                        data = await cog.get_data(
                            ajs["result"]["context"][data_file]["file"]
                        )
                        data_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(data_path, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=4)
        except (json.JSONDecodeError, binascii.Error, ValueError):
            self.LOGGER.info(
                "%s server is unavailable. Skipping...", game_details["name"]
            )
            return
        except Exception as e:
            self.LOGGER.exception(str(e))
            return


async def setup(bot: "dBot") -> None:
    await bot.add_cog(DalcomSync(bot))
