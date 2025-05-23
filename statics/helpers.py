# pyright: reportMissingModuleSource=false

import asyncio
import json
from base64 import b64decode, b64encode
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any

import discord
from aiohttp import ClientResponse
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad, unpad
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from statics.consts import AES_KEY, MAX_RETRIES
from statics.services import (  # noqa: F401
    driveService,
    sheetServiceDefault,
    sheetServiceKR,
)

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3 import File, FileList
    from googleapiclient._apis.sheets.v4 import SheetsResource


def get_sheet_data(
    spreadsheet_id: str,
    range_str: str,
    instance: str | None = None,
) -> list[list[str]]:
    _sheetService: "SheetsResource.SpreadsheetsResource.ValuesResource" = globals()[
        f"sheetService{instance or "Default"}"
    ]
    result = _sheetService.get(
        spreadsheetId=spreadsheet_id,
        range=range_str,
    ).execute(num_retries=MAX_RETRIES)
    return result.get("values", [])


def update_sheet_data(
    spreadsheet_id: str,
    range_str: str,
    parse_input: bool,
    data: list[list[str]],
    instance: str | None = None,
) -> None:
    _sheetService: "SheetsResource.SpreadsheetsResource.ValuesResource" = globals()[
        f"sheetService{instance or "Default"}"
    ]

    _sheetService.update(
        spreadsheetId=spreadsheet_id,
        range=range_str,
        valueInputOption="USER_ENTERED" if parse_input else "RAW",
        body={"values": data},
    ).execute(num_retries=MAX_RETRIES)


def clear_sheet_data(
    spreadsheet_id: str,
    range_str: str,
    instance: str | None = None,
) -> None:
    _sheetService: "SheetsResource.SpreadsheetsResource.ValuesResource" = globals()[
        f"sheetService{instance or "Default"}"
    ]

    _sheetService.clear(
        spreadsheetId=spreadsheet_id,
        range=range_str,
        body={},
    ).execute(num_retries=MAX_RETRIES)


def create_drive_data_file(data: "MediaFileUpload", metadata: "File") -> None:
    driveService.create(
        body=metadata,
        media_body=data,
    ).execute(num_retries=MAX_RETRIES)


def get_drive_data_files() -> "FileList":
    return driveService.list(
        q="'1yugfZQu3T8G9sC6WQR_YzK7bXhpdXoy4' in parents and trashed=False"
    ).execute(num_retries=MAX_RETRIES)


def get_drive_file(file_id: str, path: Path) -> None:
    request = driveService.get_media(fileId=file_id)
    file = BytesIO()
    downloader = MediaIoBaseDownload(file, request)
    done = False
    while done is False:
        _, done = downloader.next_chunk(num_retries=MAX_RETRIES)

    with open(path, "wb") as f:
        f.write(file.getbuffer())
    file.close()


def get_drive_file_last_modified(file_id: str) -> datetime:
    return datetime.strptime(
        driveService.get(  # pyright: ignore[reportTypedDictNotRequiredAccess]
            fileId=file_id, fields="modifiedTime"
        ).execute(num_retries=MAX_RETRIES)["modifiedTime"],
        "%Y-%m-%dT%H:%M:%S.%fZ",
    )


def update_drive_data_file(file_id: str, data: "MediaFileUpload") -> None:
    driveService.update(
        fileId=file_id,
        media_body=data,
    ).execute(num_retries=MAX_RETRIES)


def decrypt_ecb(data: str | bytes) -> bytes:
    cipherECB = AES.new(AES_KEY, AES.MODE_ECB)
    return unpad(cipherECB.decrypt(b64decode(data)), AES.block_size)


def decrypt_cbc(data: str | bytes, iv: str | bytes) -> bytes:
    if isinstance(iv, str):
        iv = iv.encode()

    cipherCBC = AES.new(AES_KEY, AES.MODE_CBC, iv)
    return unpad(cipherCBC.decrypt(b64decode(data)), AES.block_size)


def encrypt_cbc(data: str | bytes, iv: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode()
    if isinstance(iv, str):
        iv = iv.encode()

    cipherCBC = AES.new(AES_KEY, AES.MODE_CBC, iv)
    return b64encode(cipherCBC.encrypt(pad(data, AES.block_size))).decode()


async def pin_new_ssl(
    embed: discord.Embed,
    pin_channel: discord.TextChannel,
) -> int:
    msg = await pin_channel.send(embed=embed)
    await asyncio.sleep(1)
    await msg.pin()
    return msg.id


async def unpin_old_ssl(
    embed_title: str, pin_channel: discord.TextChannel, new_pin: int
) -> None:
    pins = await pin_channel.pins()
    for pin in pins:
        if pin.id == new_pin:
            continue

        embeds = pin.embeds
        if embeds and embeds[0].title and embed_title in embeds[0].title:
            await pin.unpin()
            break


async def get_ss_json(response: ClientResponse, iv: str | bytes) -> dict[str, Any]:
    try:
        result = await response.json(content_type=None)
    except json.JSONDecodeError:
        result = json.loads(decrypt_cbc(await response.text(), iv))
    return result


def get_column_letter(index: int) -> str:
    return chr((index) % 26 + ord("A"))
