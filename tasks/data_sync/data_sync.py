# mypy: disable-error-code="assignment"
# pyright: reportAssignmentType=false, reportTypedDictNotRequiredAccess=false

import json
import logging
from collections import defaultdict
from datetime import time
from typing import TYPE_CHECKING

from discord.ext import commands, tasks
from googleapiclient.http import MediaFileUpload

from statics.consts import Data
from statics.types import LastAppearance

from .commons import DATA_FOLDER

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3 import File

    from dBot import dBot
    from helpers.google_drive import GoogleDrive


class DataSync(commands.Cog):
    LOGGER = logging.getLogger(__name__.rpartition(".")[0])

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        try:
            await self.bot.load_extension("helpers.google_drive")
        except commands.ExtensionAlreadyLoaded:
            pass
        await self.data_download()
        self.data_upload.start()

    async def cog_unload(self) -> None:
        try:
            await self.bot.load_extension("helpers.google_drive")
        except commands.ExtensionAlreadyLoaded:
            pass
        self.save_last_appearance()
        self.save_data(Data.SSLEAGUES)
        self.data_upload.cancel()
        await self.data_upload()
        await self.bot.unload_extension("helpers.google_drive")

    async def data_download(self) -> None:
        cog: "GoogleDrive" = self.bot.get_cog("GoogleDrive")
        drive_files = await cog.get_file_list(DATA_FOLDER)
        if Data.LAST_MODIFIED.value.exists():
            with open(Data.LAST_MODIFIED.value, "r", encoding="utf-8") as f:
                last_modified = json.load(f)
        else:
            last_modified = {}

        for data_name in Data:
            data = data_name.value
            for file in drive_files["files"]:
                if file["name"] != data.name:
                    continue

                if data.exists():
                    self.LOGGER.info("Checking %s...", data.name)
                    last_modified_local = last_modified.get(data.name, 0)
                    last_modified_drive = (
                        await cog.get_file_last_modified(file["id"])
                    ).timestamp()

                    if last_modified_local >= last_modified_drive:
                        continue

                self.LOGGER.info("Downloading %s...", data.name)
                data.parent.mkdir(parents=True, exist_ok=True)
                await cog.get_file(file["id"], data)
                break

        if Data.WORD_PINGS.value.exists():
            self.bot.word_pings.clear()
            with open(Data.WORD_PINGS.value, "r", encoding="utf-8") as f:
                self.bot.word_pings = json.load(f)

            self.bot.word_pings = defaultdict(
                lambda: defaultdict(lambda: defaultdict(dict)), self.bot.word_pings
            )
            for key in self.bot.word_pings:
                self.bot.word_pings[key] = defaultdict(
                    lambda: defaultdict(dict), self.bot.word_pings[key]
                )
                for subkey in self.bot.word_pings[key]:
                    self.bot.word_pings[key][subkey] = defaultdict(
                        dict, self.bot.word_pings[key][subkey]
                    )
        else:
            Data.WORD_PINGS.value.parent.mkdir(parents=True, exist_ok=True)
            self.save_data(Data.WORD_PINGS)

        if Data.ROLES.value.exists():
            self.bot.roles.clear()
            with open(Data.ROLES.value, "r", encoding="utf-8") as f:
                self.bot.roles = json.load(f)

            self.bot.roles = defaultdict(list[int], self.bot.roles)
        else:
            Data.ROLES.value.parent.mkdir(parents=True, exist_ok=True)
            self.save_data(Data.ROLES)

        if Data.SSLEAGUES.value.exists():
            self.bot.ssleagues.clear()
            with open(Data.SSLEAGUES.value, "r", encoding="utf-8") as f:
                self.bot.ssleagues = json.load(f)

            self.bot.ssleagues = defaultdict(
                lambda: defaultdict(
                    lambda: LastAppearance(songs=defaultdict(lambda: None), date=None),
                ),
                self.bot.ssleagues,
            )
            for key in self.bot.ssleagues:
                self.bot.ssleagues[key] = defaultdict(
                    lambda: LastAppearance(songs=defaultdict(lambda: None), date=None),
                    self.bot.ssleagues[key],
                )
                for subkey in self.bot.ssleagues[key]:
                    if "songs" in self.bot.ssleagues[key][subkey]:
                        self.bot.ssleagues[key][subkey]["songs"] = defaultdict(
                            lambda: None, self.bot.ssleagues[key][subkey]["songs"]
                        )
        else:
            Data.SSLEAGUES.value.parent.mkdir(parents=True, exist_ok=True)
            self.save_data(Data.SSLEAGUES)

        if Data.LIVE_THEME.value.exists():
            self.bot.live_theme.clear()
            with open(Data.LIVE_THEME.value, "r", encoding="utf-8") as f:
                self.bot.live_theme = json.load(f)

            self.bot.live_theme = defaultdict(
                lambda: defaultdict(int), self.bot.live_theme
            )
            for key in self.bot.live_theme:
                self.bot.live_theme[key] = defaultdict(int, self.bot.live_theme[key])
        else:
            Data.LIVE_THEME.value.parent.mkdir(parents=True, exist_ok=True)
            self.save_data(Data.LIVE_THEME)

    @tasks.loop(time=[time(hour=h, minute=30) for h in range(24)])
    async def data_upload(self) -> None:
        cog: "GoogleDrive" = self.bot.get_cog("GoogleDrive")
        drive_files = await cog.get_file_list(DATA_FOLDER)
        last_modified = {}

        for data_name in Data:
            data = data_name.value
            self.LOGGER.info("Uploading %s...", data.name)
            media = MediaFileUpload(data)

            for file in drive_files["files"]:
                if file["name"] == data.name:
                    last_modified[data.name] = (
                        await cog.update_drive_file(file["id"], media)
                    ).timestamp()
                    break
            else:
                metadata: "File" = {"name": data.name, "parents": [DATA_FOLDER]}
                last_modified[data.name] = (await cog.create_file(metadata, media))[
                    1
                ].timestamp()
            data.touch(exist_ok=True)

        self.save_data(Data.LAST_MODIFIED, last_modified)

    def save_data(self, data: Data, content: dict | None = None) -> None:
        if content is None:
            content = getattr(self.bot, data.name.lower())
        with open(data.value, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=4)

    def save_last_appearance(self) -> None:
        for game in self.bot.ssleague_manual:
            target = self.bot.ssleagues[game][self.bot.ssleague_manual[game]["artist"]]
            target["songs"][self.bot.ssleague_manual[game]["songId"]] = target[
                "date"
            ] = self.bot.ssleague_manual[game]["date"]
        self.bot.ssleague_manual.clear()


async def setup(bot: "dBot") -> None:
    await bot.add_cog(DataSync(bot))
