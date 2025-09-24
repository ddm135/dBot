# pyright: reportTypedDictNotRequiredAccess=false

import asyncio
import json
from datetime import time
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks
from googleapiclient.http import MediaFileUpload

from statics.consts import GAMES, AssetScheme
from tasks.border_sync.commons import BORDER_CHANNEL, BORDER_FOLDER, FOLDER_MIME

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3 import File

    from dBot import dBot
    from helpers.google_drive import GoogleDrive
    from helpers.superstar import SuperStar


class BorderSync(commands.Cog):
    def __init__(self, bot: "dBot") -> None:
        self.bot = bot
        self.counter = 0

    async def cog_load(self) -> None:
        await self.border_sync()
        self.border_sync.start()

    async def cog_unload(self) -> None:
        self.border_sync.cancel()

    @tasks.loop(time=[time(hour=h, minute=35) for h in range(24)])
    async def border_sync(self) -> None:
        drive_cog: "GoogleDrive" = self.bot.get_cog(
            "GoogleDrive"
        )  # type: ignore[assignment]
        ss_cog: "SuperStar" = self.bot.get_cog("SuperStar")  # type: ignore[assignment]
        border_channel = self.bot.get_channel(
            BORDER_CHANNEL
        ) or await self.bot.fetch_channel(BORDER_CHANNEL)
        assert isinstance(border_channel, discord.TextChannel)
        drive_folders = await drive_cog.get_file_list(
            BORDER_FOLDER, mime_type=FOLDER_MIME
        )
        counter = 0

        for game, game_details in GAMES.items():
            if game_details["assetScheme"] not in (
                AssetScheme.BINARY_CATALOG,
                AssetScheme.JSON_CATALOG,
            ):
                continue

            with open(
                f"data/dalcom/{game}/LocaleData.json", "r", encoding="utf-8"
            ) as f:
                lcd = json.load(f)
            with open(f"data/dalcom/{game}/ThemeData.json", "r", encoding="utf-8") as f:
                tmd = json.load(f)
            with open(
                f"data/dalcom/{game}/ThemeTypeData.json", "r", encoding="utf-8"
            ) as f:
                ttd = json.load(f)

            borders = {}
            for border in ttd:
                if not border["code"]:
                    continue

                suffixes = {"_Large": ""}
                for theme in tmd:
                    if theme["themeTypeCode"] == border["code"]:
                        if theme["nameImageZoom"]:
                            suffixes["_Zoom"] = "z"
                        break
                else:
                    continue

                if not theme["limitedType"]:
                    continue

                for locale in lcd:
                    if theme["localeName"] == locale["code"]:
                        name = locale["enUS"]
                        break
                else:
                    continue

                catalog_key = Path(border["gradeR"])
                for k, v in suffixes.items():
                    border_name = f"{border["code"]}{v} - {name}{catalog_key.suffix}"
                    borders[border_name] = str(
                        catalog_key.with_stem(catalog_key.stem + k)
                    )

            for folder in drive_folders["files"]:
                if folder["name"] == game_details["name"]:
                    border_folder = folder["id"]
                    break
            else:
                metadata: "File" = {
                    "name": game_details["name"],
                    "mimeType": FOLDER_MIME,
                    "parents": [BORDER_FOLDER],
                }
                border_folder = (await drive_cog.create_file(metadata))[0]

            next_page = ""
            while True:
                border_files = await drive_cog.get_file_list(
                    border_folder, next_page=next_page
                )
                for file in border_files["files"]:
                    borders.pop(file["name"], None)
                if not (next_page := border_files.get("nextPageToken")):
                    break

            for border_name, catalog_key in borders.items():
                try:
                    border_media = MediaFileUpload(
                        await ss_cog.extract_file_from_bundle(game, catalog_key)
                    )
                except KeyError:
                    await border_channel.send(
                        f"{game_details["name"]}: {border_name} (?)"
                    )
                    continue
                metadata: "File" = {
                    "name": border_name,
                    "parents": [border_folder],
                }
                link = (await drive_cog.create_file(metadata, border_media))[2]
                await border_channel.send(
                    f"{game_details["name"]}: {border_name}\n<{link}>"
                )
                counter += 1

                if counter > 900:
                    await asyncio.sleep(100)
                    counter = 0


async def setup(bot: "dBot") -> None:
    await bot.add_cog(BorderSync(bot))
