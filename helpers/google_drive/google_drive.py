# mypy: disable-error-code="attr-defined"
# pylint: disable=no-member
# pyright: reportMissingModuleSource=false, reportTypedDictNotRequiredAccess=false

import asyncio
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from discord.ext import commands
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from statics.consts import MAX_RETRIES

from .commons import (
    SCOPES,
    SERVICE_NAME,
    STATIC_DISCOVERY,
    TIME_FORMAT,
    VERSION,
)

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3 import File, FileList

    from dBot import dBot


class GoogleDrive(commands.Cog):
    def __init__(self, bot: "dBot") -> None:
        self.bot = bot
        self.service = build(
            serviceName=SERVICE_NAME,
            version=VERSION,
            credentials=Credentials.from_service_account_file(
                filename="dBot.json",
                scopes=SCOPES,
            ),
            num_retries=MAX_RETRIES,
            static_discovery=STATIC_DISCOVERY,
        ).files()  # pyright: ignore[reportAttributeAccessIssue]

    async def create_file(
        self, metadata: "File", data: "MediaFileUpload | None" = None
    ) -> tuple[str, datetime, str]:
        result = await asyncio.to_thread(
            self.service.create(
                body=metadata, media_body=data, fields="id,modifiedTime,webViewLink"
            ).execute,
            num_retries=MAX_RETRIES,
        )
        return (
            result["id"],
            datetime.strptime(
                result["modifiedTime"],
                TIME_FORMAT,
            ),
            result["webViewLink"],
        )

    async def get_file_list(
        self, parent: str, *, mime_type: str | None = None, next_page: str = ""
    ) -> "FileList":
        return await asyncio.to_thread(
            self.service.list(
                q=(
                    f"'{parent}' in parents and trashed=False"
                    f"{f" and mimeType='{mime_type}'" if mime_type else ""}"
                ),
                pageToken=next_page,
            ).execute,
            num_retries=MAX_RETRIES,
        )

    async def get_file(self, file_id: str, path: Path) -> None:
        request = self.service.get_media(fileId=file_id)
        file = BytesIO()
        downloader = MediaIoBaseDownload(file, request)
        done = False
        while done is False:
            _, done = await asyncio.to_thread(
                downloader.next_chunk, num_retries=MAX_RETRIES
            )

        with open(path, "wb") as f:
            f.write(file.getbuffer())
        file.close()

    async def get_file_last_modified(self, file_id: str) -> datetime:
        result = await asyncio.to_thread(
            self.service.get(fileId=file_id, fields="modifiedTime").execute,
            num_retries=MAX_RETRIES,
        )
        return datetime.strptime(
            result["modifiedTime"],
            TIME_FORMAT,
        )

    async def update_drive_file(
        self, file_id: str, data: "MediaFileUpload"
    ) -> datetime:
        result = await asyncio.to_thread(
            self.service.update(
                fileId=file_id, media_body=data, fields="modifiedTime"
            ).execute,
            num_retries=MAX_RETRIES,
        )
        return datetime.strptime(
            result["modifiedTime"],
            TIME_FORMAT,
        )


async def setup(bot: "dBot") -> None:
    await bot.add_cog(GoogleDrive(bot))
