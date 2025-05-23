# pyright: reportTypedDictNotRequiredAccess=false
# pyright: reportArgumentType=false

import json
import logging
from collections import defaultdict
from datetime import datetime, time
from typing import TYPE_CHECKING

from discord.ext import commands, tasks
from googleapiclient.http import MediaFileUpload

from statics.consts import CREDENTIALS_DATA, PING_DATA, ROLE_DATA
from statics.helpers import (
    create_drive_data_file,
    get_drive_data_files,
    get_drive_file,
    get_drive_file_last_modified,
    update_drive_data_file,
)

if TYPE_CHECKING:
    from dBot import dBot


class DataSync(commands.Cog):
    DATA = [PING_DATA, ROLE_DATA, CREDENTIALS_DATA]
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

                self.LOGGER.info(f"Downloading {data.name}...")
                data.parent.mkdir(parents=True, exist_ok=True)
                get_drive_file(file["id"], data)
                break

        if PING_DATA.exists():
            self.bot.pings.clear()
            with open(PING_DATA, "r") as f:
                self.bot.pings = json.load(f)

            self.bot.pings = defaultdict(
                lambda: defaultdict(
                    lambda: defaultdict(dict),  # type: ignore[arg-type]
                ),
                self.bot.pings,
            )
            for key in self.bot.pings:
                self.bot.pings[key] = defaultdict(
                    lambda: defaultdict(dict),  # type: ignore[arg-type]
                    self.bot.pings[key],
                )
                for subkey in self.bot.pings[key]:
                    self.bot.pings[key][subkey] = defaultdict(
                        dict,  # type: ignore[arg-type]
                        self.bot.pings[key][subkey],
                    )
        else:
            PING_DATA.parent.mkdir(parents=True, exist_ok=True)
            with open(PING_DATA, "w") as f:
                json.dump(self.bot.pings, f, indent=4)

        if ROLE_DATA.exists():
            self.bot.roles.clear()
            with open(ROLE_DATA, "r") as f:
                self.bot.roles = json.load(f)

            self.bot.roles = defaultdict(list[int], self.bot.roles)
        else:
            ROLE_DATA.parent.mkdir(parents=True, exist_ok=True)
            with open(ROLE_DATA, "w") as f:
                json.dump(self.bot.roles, f, indent=4)

    @tasks.loop(time=time(hour=10))
    async def data_upload(self) -> None:
        drive_files = get_drive_data_files()
        for data in self.DATA:
            self.LOGGER.info(f"Uploading {data.name}...")
            media = MediaFileUpload(data)

            for file in drive_files["files"]:
                if file["name"] == data.name:
                    update_drive_data_file(file["id"], data=media)
                    break
            else:
                metadata = {
                    "name": data.name,
                    "parents": [self.FOLDER],
                }
                create_drive_data_file(
                    data=media,
                    metadata=metadata,  # type: ignore[arg-type]
                )

            data.touch(exist_ok=True)

    @data_upload.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: "dBot") -> None:
    await bot.add_cog(DataSync(bot))
