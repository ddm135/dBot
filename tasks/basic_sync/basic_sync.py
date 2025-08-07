import asyncio
import json
import logging
from datetime import time
from pathlib import Path
from typing import TYPE_CHECKING

import aiohttp
from discord.ext import commands, tasks

from statics.consts import GAMES, AssetScheme

if TYPE_CHECKING:
    from dBot import dBot


class BasicSync(commands.Cog):
    LOGGER = logging.getLogger(__name__.rpartition(".")[0])

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await self.basic_sync()
        self.basic_sync.start()

    async def cog_unload(self) -> None:
        self.basic_sync.cancel()
        self.bot.bonus.clear()

    @tasks.loop(time=[time(hour=h, minute=5) for h in range(24)])
    async def basic_sync(self) -> None:
        for game, game_details in GAMES.items():
            if not (query := game_details.get("lookupQuery")) or not (
                manifest_url := game_details.get("manifestUrl")
            ):
                continue
            self.LOGGER.info("Downloading basic data: %s...", game_details["name"])

            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://itunes.apple.com/lookup?{query}") as r:
                    result = await r.text()
                    encoded_result = result.replace("\n", "")
                    new_result = json.loads(encoded_result)
                    self.bot.basic[game]["version"] = new_result["results"][0][
                        "version"
                    ]

                async with session.get(
                    manifest_url.format(version=self.bot.basic[game]["version"])
                ) as r:
                    self.bot.basic[game]["manifest"] = await r.json(content_type=None)

                if game_details["assetScheme"] != AssetScheme.BINARY_CATALOG or not (
                    catalog_url := game_details.get("catalogUrl")
                ):
                    continue

                resource_version = self.bot.basic[game]["manifest"]["ResourceVersion"]
                catalog_folder_path = Path(f"data/catalogs/{game}")
                catalog_folder_path.mkdir(parents=True, exist_ok=True)
                catalog_bin_path = catalog_folder_path / f"{resource_version}.bin"
                catalog_json_path = catalog_folder_path / f"{resource_version}.json"

                if not catalog_json_path.exists():
                    if not catalog_bin_path.exists():
                        for file in catalog_folder_path.iterdir():
                            if file.is_file():
                                file.unlink()

                        async with session.get(
                            catalog_url.format(version=resource_version)
                        ) as r:
                            with open(catalog_bin_path, "wb") as f:
                                f.write(await r.read())

                    process = await asyncio.create_subprocess_exec(
                        "utils/catalog",
                        str(catalog_bin_path),
                        str(catalog_json_path),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await process.communicate()
                    self.bot.basic[game]["catalog"] = {}

                if not self.bot.basic[game].get("catalog"):
                    with open(catalog_json_path, "r", encoding="utf-8") as f:
                        self.bot.basic[game]["catalog"] = json.load(f)


async def setup(bot: "dBot") -> None:
    await bot.add_cog(BasicSync(bot))
