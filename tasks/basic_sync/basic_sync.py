import asyncio
import json
import logging
from datetime import time
from pathlib import Path
from typing import TYPE_CHECKING

import aiohttp
from discord.ext import commands, tasks

from statics.consts import GAMES, AssetScheme
from statics.types import BasicDetails

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
        self.bot.basic.clear()

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
                    weird_result = await r.text()
                    text_result = weird_result.replace("\n", "")
                    json_result = json.loads(text_result)
                    version = json_result["results"][0]["version"]
                    iconUrl = json_result["results"][0]["artworkUrl100"]

                async with session.get(manifest_url.format(version=version)) as r:
                    manifest = await r.json(content_type=None)

                self.bot.basic[game] = BasicDetails(
                    version=version,
                    iconUrl=iconUrl,
                    manifest=manifest,
                )
                if game_details["assetScheme"] not in (
                    AssetScheme.BINARY_CATALOG,
                    AssetScheme.JSON_CATALOG,
                ) or not (catalog_url := game_details.get("catalogUrl")):
                    continue

                resource_version = manifest["ResourceVersion"]
                catalog_folder_path = Path(f"data/catalogs/{game}")
                catalog_folder_path.mkdir(parents=True, exist_ok=True)
                extension = (
                    "bin"
                    if game_details["assetScheme"] == AssetScheme.BINARY_CATALOG
                    else "json"
                )
                catalog_packaged_path = (
                    catalog_folder_path / f"{resource_version}.{extension}"
                )
                catalog_extracted_path = (
                    catalog_folder_path / f"{resource_version}_extracted.json"
                )

                if not catalog_extracted_path.exists():
                    for file in catalog_folder_path.iterdir():
                        if file.is_file():
                            file.unlink()

                    async with session.get(
                        catalog_url.format(version=resource_version)
                    ) as r:
                        with open(catalog_packaged_path, "wb") as f:
                            f.write(await r.read())

                    process = await asyncio.create_subprocess_exec(
                        f"utils/catalog-{extension}",
                        str(catalog_packaged_path),
                        str(catalog_extracted_path),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await process.communicate()

                    with open(catalog_extracted_path, "r", encoding="utf-8") as f:
                        self.bot.basic[game]["catalog"] = json.load(f)

                if "catalog" not in self.bot.basic[game]:
                    with open(catalog_extracted_path, "r", encoding="utf-8") as f:
                        self.bot.basic[game]["catalog"] = json.load(f)


async def setup(bot: "dBot") -> None:
    await bot.add_cog(BasicSync(bot))
