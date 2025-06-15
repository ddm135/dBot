# pyright: reportTypedDictNotRequiredAccess=false
# pyright: reportArgumentType=false

import json
import logging
from collections import defaultdict
from datetime import datetime, time
from pathlib import Path
from typing import TYPE_CHECKING

from discord.ext import commands, tasks
from googleapiclient.http import MediaFileUpload

from statics.consts import TIMEZONES
from statics.helpers import (
    create_drive_data_file,
    get_drive_data_files,
    get_drive_file,
    get_drive_file_last_modified,
    update_drive_data_file,
)
from statics.types import LastAppearance

if TYPE_CHECKING:
    from dBot import dBot


class DataSync(commands.Cog):
    CREDENTIAL_DATA = Path("data/credentials.json")
    PING_DATA = Path("data/pings.json")
    ROLE_DATA = Path("data/roles.json")
    SSLEAGUE_DATA = Path("data/ssleague.json")
    DATA = [ROLE_DATA, PING_DATA, CREDENTIAL_DATA, SSLEAGUE_DATA]
    FOLDER = "1yugfZQu3T8G9sC6WQR_YzK7bXhpdXoy4"
    LOGGER = logging.getLogger(__name__)

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.data_download()
        self.data_upload.start()

    async def cog_unload(self) -> None:
        self.data_upload.cancel()
        await self.data_upload()

    def data_download(self) -> None:
        drive_files = get_drive_data_files()
        for data in self.DATA:
            for file in drive_files["files"]:
                if file["name"] != data.name:
                    continue

                last_modified = get_drive_file_last_modified(file["id"])
                if data.exists() and last_modified <= datetime.fromtimestamp(
                    data.stat().st_mtime
                ):
                    continue

                self.LOGGER.info("Downloading %s...", data.name)
                data.parent.mkdir(parents=True, exist_ok=True)
                get_drive_file(file["id"], data)
                break

        if self.CREDENTIAL_DATA.exists():
            self.bot.credentials.clear()
            with open(self.CREDENTIAL_DATA, "r", encoding="utf-8") as f:
                self.bot.credentials = json.load(f)

        if self.PING_DATA.exists():
            self.bot.pings.clear()
            with open(self.PING_DATA, "r", encoding="utf-8") as f:
                self.bot.pings = json.load(f)

            self.bot.pings = defaultdict(
                lambda: defaultdict(
                    lambda: defaultdict(dict),
                ),
                self.bot.pings,
            )
            for key in self.bot.pings:
                self.bot.pings[key] = defaultdict(
                    lambda: defaultdict(dict),
                    self.bot.pings[key],
                )
                for subkey in self.bot.pings[key]:
                    self.bot.pings[key][subkey] = defaultdict(
                        dict,
                        self.bot.pings[key][subkey],
                    )
        else:
            self.PING_DATA.parent.mkdir(parents=True, exist_ok=True)
            self.save_ping_data()

        if self.ROLE_DATA.exists():
            self.bot.roles.clear()
            with open(self.ROLE_DATA, "r", encoding="utf-8") as f:
                self.bot.roles = json.load(f)

            self.bot.roles = defaultdict(list[int], self.bot.roles)
        else:
            self.ROLE_DATA.parent.mkdir(parents=True, exist_ok=True)
            self.save_role_data()

        if self.SSLEAGUE_DATA.exists():
            self.bot.ssleague.clear()
            with open(self.SSLEAGUE_DATA, "r", encoding="utf-8") as f:
                self.bot.ssleague = json.load(f)

            self.bot.ssleague = defaultdict(
                lambda: defaultdict(
                    lambda: LastAppearance(songs=defaultdict(lambda: None), date=None),
                ),
                self.bot.ssleague,
            )
            for key in self.bot.ssleague:
                self.bot.ssleague[key] = defaultdict(
                    lambda: LastAppearance(songs=defaultdict(lambda: None), date=None),
                    self.bot.ssleague[key],
                )
                for subkey in self.bot.ssleague[key]:
                    if "songs" in self.bot.ssleague[key][subkey]:
                        self.bot.ssleague[key][subkey]["songs"] = defaultdict(
                            lambda: None,
                            self.bot.ssleague[key][subkey]["songs"],
                        )
        else:
            self.SSLEAGUE_DATA.parent.mkdir(parents=True, exist_ok=True)
            self.save_ssleague_data()

    @tasks.loop(time=time(hour=1, tzinfo=TIMEZONES["KST"]))
    async def data_upload(self) -> None:
        self.save_last_appearance()
        self.save_ssleague_data()

        drive_files = get_drive_data_files()
        for data in self.DATA:
            self.LOGGER.info("Uploading %s...", data.name)
            media = MediaFileUpload(data)

            for file in drive_files["files"]:
                if file["name"] == data.name:
                    update_drive_data_file(file["id"], media)
                    break
            else:
                metadata = {
                    "name": data.name,
                    "parents": [self.FOLDER],
                }
                create_drive_data_file(
                    media,
                    metadata,  # type: ignore[arg-type]
                )

            data.touch(exist_ok=True)

    def save_credential_data(self) -> None:
        with open(self.CREDENTIAL_DATA, "w", encoding="utf-8") as f:
            json.dump(self.bot.credentials, f, indent=4)

    def save_ping_data(self) -> None:
        with open(self.PING_DATA, "w", encoding="utf-8") as f:
            json.dump(self.bot.pings, f, indent=4)

    def save_role_data(self) -> None:
        with open(self.ROLE_DATA, "w", encoding="utf-8") as f:
            json.dump(self.bot.roles, f, indent=4)

    def save_ssleague_data(self) -> None:
        with open(self.SSLEAGUE_DATA, "w", encoding="utf-8") as f:
            json.dump(self.bot.ssleague, f, indent=4)

    def save_last_appearance(self) -> None:
        for game in self.bot.ssleague_manual:
            target = self.bot.ssleague[game][self.bot.ssleague_manual[game]["artist"]]
            date = self.bot.ssleague_manual[game]["date"]
            target["songs"][self.bot.ssleague_manual[game]["song_id"]] = date
            target["date"] = date
        self.bot.ssleague_manual.clear()

    @data_upload.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: "dBot") -> None:
    await bot.add_cog(DataSync(bot))
