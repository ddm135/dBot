import json
import logging
from collections import defaultdict
from datetime import time
from typing import TYPE_CHECKING

from discord.ext import commands, tasks
from googleapiclient.http import MediaFileUpload

from statics.consts import Data
from statics.types import LastAppearance

if TYPE_CHECKING:
    from dBot import dBot


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
        cog = self.bot.get_cog("GoogleDrive")
        drive_files = await cog.get_file_list()  # type: ignore[union-attr]
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
                        await cog.get_file_last_modified(  # type: ignore[union-attr]
                            file["id"]
                        )
                    ).timestamp()

                    if last_modified_local >= last_modified_drive:
                        continue

                self.LOGGER.info("Downloading %s...", data.name)
                data.parent.mkdir(parents=True, exist_ok=True)
                await cog.get_file(file["id"], data)  # type: ignore[union-attr]
                break

        if Data.CREDENTIALS.value.exists():
            self.bot.credentials.clear()
            with open(Data.CREDENTIALS.value, "r", encoding="utf-8") as f:
                self.bot.credentials = json.load(f)

        if Data.WORD_PINGS.value.exists():
            self.bot.word_pings.clear()
            with open(Data.WORD_PINGS.value, "r", encoding="utf-8") as f:
                self.bot.word_pings = json.load(f)

            self.bot.word_pings = defaultdict(
                lambda: defaultdict(
                    lambda: defaultdict(dict),
                ),
                self.bot.word_pings,
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

    @tasks.loop(time=[time(hour=h, minute=30) for h in range(24)])
    async def data_upload(self) -> None:
        cog = self.bot.get_cog("GoogleDrive")
        drive_files = await cog.get_file_list()  # type: ignore[union-attr]
        last_modified = {}

        for data_name in Data:
            data = data_name.value
            self.LOGGER.info("Uploading %s...", data.name)
            media = MediaFileUpload(data)

            for file in drive_files["files"]:
                if file["name"] == data.name:
                    last_modified[data.name] = (
                        await cog.update_drive_file(  # type: ignore[union-attr]
                            file["id"], media
                        )
                    ).timestamp()
                    break
            else:
                metadata = {"name": data.name}
                last_modified[data.name] = (
                    await cog.create_file(media, metadata)  # type: ignore[union-attr]
                ).timestamp()
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
