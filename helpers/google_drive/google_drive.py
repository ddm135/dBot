# mypy: disable-error-code="attr-defined"
# pylint: disable=no-member
# pyright: reportMissingModuleSource=false, reportTypedDictNotRequiredAccess=false

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
    DATA_FOLDER,
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
                filename="dBotDefault.json",
                scopes=SCOPES,
            ),
            num_retries=MAX_RETRIES,
            static_discovery=STATIC_DISCOVERY,
        ).files()

    def create_drive_file(self, data: "MediaFileUpload", metadata: "File") -> datetime:
        metadata["parents"] = [DATA_FOLDER]
        return datetime.strptime(
            self.service.create(
                body=metadata, media_body=data, fields="modifiedTime"
            ).execute(num_retries=MAX_RETRIES)["modifiedTime"],
            TIME_FORMAT,
        )

    def get_drive_files(self) -> "FileList":
        return self.service.list(
            q=f"'{DATA_FOLDER}' in parents and trashed=False"
        ).execute(num_retries=MAX_RETRIES)

    def get_drive_file(self, file_id: str, path: Path) -> None:
        request = self.service.get_media(fileId=file_id)
        file = BytesIO()
        downloader = MediaIoBaseDownload(file, request)
        done = False
        while done is False:
            _, done = downloader.next_chunk(num_retries=MAX_RETRIES)

        with open(path, "wb") as f:
            f.write(file.getbuffer())
        file.close()

    def get_drive_file_last_modified(self, file_id: str) -> datetime:
        return datetime.strptime(
            self.service.get(fileId=file_id, fields="modifiedTime").execute(
                num_retries=MAX_RETRIES
            )["modifiedTime"],
            TIME_FORMAT,
        )

    def update_drive_file(self, file_id: str, data: "MediaFileUpload") -> datetime:
        return datetime.strptime(
            self.service.update(
                fileId=file_id, media_body=data, fields="modifiedTime"
            ).execute(num_retries=MAX_RETRIES)["modifiedTime"],
            TIME_FORMAT,
        )


async def setup(bot: "dBot") -> None:
    await bot.add_cog(GoogleDrive(bot))
