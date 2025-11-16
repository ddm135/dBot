# pyright: reportTypedDictNotRequiredAccess=false

import binascii
import json
import logging
from datetime import time
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks
from googleapiclient.http import MediaFileUpload

from statics.consts import GAMES, AssetScheme

from .commons import BORDER_CHANNEL, BORDER_FOLDER, FOLDER_MIME

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3 import File

    from dBot import dBot
    from helpers.google_drive import GoogleDrive
    from helpers.superstar import SuperStar


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

        for game, game_details in GAMES.items():
            try:
                if not (basic_details := self.bot.basic.get(game)):
                    continue
                ajs_path = Path(f"data/dalcom/{game}/a.json")
                if ajs_path.exists():
                    with open(ajs_path, "r", encoding="utf-8") as f:
                        stored_ajs = json.load(f)
                else:
                    stored_ajs = None

                self.LOGGER.info("Downloading Dalcom data: %s...", game_details["name"])
                ajs = await ss_cog.get_a_json(basic_details)
                refresh = False

                if ajs["code"] != 1000:
                    ajs = stored_ajs
                elif (
                    not stored_ajs
                    or ajs["result"]["version"] != stored_ajs["result"]["version"]
                ):
                    ajs_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(ajs_path, "w", encoding="utf-8") as f:
                        json.dump(ajs, f, indent=4)
                    refresh = True
                if not ajs:
                    continue

                data_files = [
                    "GroupData",
                    "LocaleData",
                    "MusicData",
                    "ThemeData",
                    "ThemeTypeData",
                ]
                if game_details["assetScheme"] == AssetScheme.JSON_URL:
                    data_files.append("URLs")
                lcd = tmd = ttd = None
                for data_file in data_files:
                    data_path = Path(f"data/dalcom/{game}/{data_file}.json")
                    if (
                        not stored_ajs
                        or ajs["result"]["context"][data_file]["version"]
                        != stored_ajs["result"]["context"][data_file]["version"]
                        or refresh
                        or not data_path.exists()
                    ):
                        data = await ss_cog.get_data(
                            ajs["result"]["context"][data_file]["file"]
                        )
                        data_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(data_path, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=4)
                    else:
                        with open(data_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                    match data_file:
                        case "LocaleData":
                            lcd = data
                        case "ThemeData":
                            tmd = data
                        case "ThemeTypeData":
                            ttd = data
                        case _:
                            pass

                if not (lcd and tmd and ttd) or game_details["assetScheme"] not in (
                    AssetScheme.BINARY_CATALOG,
                    AssetScheme.JSON_CATALOG,
                ):
                    continue

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
                        border_name = (
                            f"{border["code"]}{v} - {name}{catalog_key.suffix}"
                        )
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
                    if not (next_page := border_files.get("nextPageToken", "")):
                        break

                if borders:
                    self.LOGGER.info("Uploading borders: %s...", game_details["name"])
                    for border_name, border_key in borders.items():
                        try:
                            border_file_path = await ss_cog.extract_file_from_bundle(
                                game, border_key
                            )
                            border_media = MediaFileUpload(border_file_path)
                        except KeyError:
                            continue
                        metadata = {"name": border_name, "parents": [border_folder]}
                        link = (await drive_cog.create_file(metadata, border_media))[2]
                        await border_channel.send(
                            f"{game_details["name"]}: "
                            f"{border_name.replace(r"<", r"\<")}\n<{link}>"
                        )

            except (json.JSONDecodeError, binascii.Error, ValueError):
                self.LOGGER.info(
                    "%s server is unavailable. Skipping...", game_details["name"]
                )
                continue
            except Exception as e:
                self.LOGGER.exception(str(e))
                continue


async def setup(bot: "dBot") -> None:
    await bot.add_cog(DalcomSync(bot))
