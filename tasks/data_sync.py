# pyright: reportTypedDictNotRequiredAccess=false

import logging
from datetime import time
from typing import TYPE_CHECKING

from discord.ext import commands, tasks
from googleapiclient.http import MediaFileUpload

from statics.consts import PING_DATA, ROLE_DATA
from statics.helpers import (
    create_drive_data_file,
    get_drive_data_file,
    get_drive_data_files,
    update_drive_data_file,
)

if TYPE_CHECKING:
    from dBot import dBot


class DataSync(commands.Cog):
    data = [PING_DATA, ROLE_DATA]
    data_folder = "1yugfZQu3T8G9sC6WQR_YzK7bXhpdXoy4"
    LOGGER = logging.getLogger(__name__)

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.data_download()
        self.data_upload.start()
        await super().cog_load()

    async def cog_unload(self) -> None:
        self.data_upload.cancel()
        await self.data_upload()
        await super().cog_unload()

    def data_download(self) -> None:
        drive_files = get_drive_data_files()
        for data in self.data:
            if data.exists():
                continue

            self.LOGGER.info(f"Downloading {data.name}...")
            for file in drive_files["files"]:
                if file["name"] == data.name:
                    get_drive_data_file(file["id"], data)
                    break

    @tasks.loop(time=time(hour=10))
    async def data_upload(self) -> None:
        drive_files = get_drive_data_files()
        for data in self.data:
            self.LOGGER.info(f"Uploading {data.name}...")
            media = MediaFileUpload(data)
            for file in drive_files["files"]:
                if file["name"] == data.name:
                    update_drive_data_file(file["id"], data=media)
                    break
            else:
                metadata = {
                    "name": data.name,
                    "parents": [self.data_folder],
                }
                create_drive_data_file(data=media, metadata=metadata)  # type: ignore

    @data_upload.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: "dBot") -> None:
    await bot.add_cog(DataSync(bot))
