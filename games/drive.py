"""The Google Drive folder that borders are kept in, one subfolder per game.

Borders are announced once. What is already in a game's folder is what has
been announced, so the folder is the record: nothing else needs storing. Each
file carries where it came from (the catalog key and id), so a border the game
republishes under the same name is noticed: the old file is renamed
"<number> (old) - <name>" and the new one takes its name.
"""

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol, Self

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
FOLDER_MIME = "application/vnd.google-apps.folder"
RETRIES = 3


SOURCE = "source"  # the file property that says where a border came from


def fingerprint(source: str) -> str:
    """A short stand-in for a source: Drive limits a property (key and value
    together) to 124 bytes, which a catalog key and an asset path can pass."""
    return hashlib.sha256(source.encode()).hexdigest()[:32]


@dataclass(frozen=True, slots=True)
class StoredFile:
    id: str
    source: str | None  # None for a file uploaded before sources were recorded


class BorderFolder(Protocol):
    """What the border task needs of the folder."""

    async def game_folder(self, name: str) -> str: ...

    async def files(self, folder: str) -> dict[str, StoredFile]: ...

    async def upload(
        self, folder: str, name: str, data: bytes, source: str = ""
    ) -> str: ...

    async def rename(self, file_id: str, name: str) -> None: ...


def _quote(text: str) -> str:
    return text.replace("\\", "\\\\").replace("'", "\\'")


class Drive:
    def __init__(self, root: str, files: Any) -> None:
        """``files`` is the Drive API's ``files()`` resource."""
        self._root = root
        self._files = files

    @classmethod
    def from_service_account(cls, root: str, credentials_file: Path) -> Self:
        credentials = Credentials.from_service_account_file(
            str(credentials_file), scopes=SCOPES
        )
        service = build(
            "drive",
            "v3",
            credentials=credentials,
            num_retries=RETRIES,
            static_discovery=True,
        )
        return cls(root, service.files())

    async def _execute(self, request: Any) -> Any:
        return await asyncio.to_thread(request.execute, num_retries=RETRIES)

    async def _list(self, query: str) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        token = ""
        while True:
            result = await self._execute(
                self._files.list(
                    q=query,
                    pageToken=token,
                    fields="nextPageToken,files(id,name,appProperties)",
                )
            )
            found.extend(result.get("files", []))
            token = result.get("nextPageToken", "")
            if not token:
                return found

    async def game_folder(self, name: str) -> str:
        """The id of the game's subfolder, made if it is not there yet."""
        folders = await self._list(
            f"'{self._root}' in parents and trashed=false and mimeType='{FOLDER_MIME}'"
        )
        for folder in folders:
            if folder["name"] == name:
                return str(folder["id"])
        made = await self._execute(
            self._files.create(
                body={"name": name, "mimeType": FOLDER_MIME, "parents": [self._root]},
                fields="id",
            )
        )
        return str(made["id"])

    async def files(self, folder: str) -> dict[str, StoredFile]:
        """The files of a folder by name, with where each came from."""
        found = await self._list(f"'{_quote(folder)}' in parents and trashed=false")
        return {
            str(f["name"]): StoredFile(
                str(f["id"]), (f.get("appProperties") or {}).get(SOURCE)
            )
            for f in found
        }

    async def upload(
        self, folder: str, name: str, data: bytes, source: str = ""
    ) -> str:
        """Upload a PNG; returns the link to view it."""
        body: dict[str, Any] = {"name": name, "parents": [folder]}
        if source:
            body["appProperties"] = {SOURCE: source}
        made = await self._execute(
            self._files.create(
                body=body,
                media_body=MediaIoBaseUpload(BytesIO(data), mimetype="image/png"),
                fields="id,webViewLink",
            )
        )
        return str(made["webViewLink"])

    async def rename(self, file_id: str, name: str) -> None:
        """Give an existing file a new name."""
        await self._execute(
            self._files.update(fileId=file_id, body={"name": name}, fields="id")
        )
