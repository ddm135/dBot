# pyright: reportMissingModuleSource=false

import asyncio
import json
from base64 import b64decode, b64encode
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from aiohttp import ClientResponse
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad, unpad
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from statics.consts import AES_KEY, MAX_RETRIES

# pylint: disable-next=unused-import
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
    sheetService: "SheetsResource.SpreadsheetsResource" = globals()[
        f"sheetService{instance or "Default"}"
    ]
    result = (
        sheetService.values()
        .get(
            spreadsheetId=spreadsheet_id,
            range=range_str,
        )
        .execute(num_retries=MAX_RETRIES)
    )
    return result.get("values", [])


def update_sheet_data(
    spreadsheet_id: str,
    range_str: str,
    data: list[list[str]],
    parse_input: bool,
    instance: str | None = None,
) -> None:
    sheetService: "SheetsResource.SpreadsheetsResource" = globals()[
        f"sheetService{instance or "Default"}"
    ]

    sheetService.values().update(
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
    sheetService: "SheetsResource.SpreadsheetsResource" = globals()[
        f"sheetService{instance or "Default"}"
    ]

    sheetService.values().clear(
        spreadsheetId=spreadsheet_id,
        range=range_str,
        body={},
    ).execute(num_retries=MAX_RETRIES)


def find_replace_sheet_data(
    spreadsheet_id: str,
    range_grid: dict[str, int | str],
    find: str,
    replace: str,
    instance: str | None = None,
) -> None:
    sheetService: "SheetsResource.SpreadsheetsResource" = globals()[
        f"sheetService{instance or "Default"}"
    ]

    sheetService.batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "findReplace": {
                        "find": find,
                        "replacement": replace,
                        "matchCase": True,
                        "matchEntireCell": True,
                        "searchByRegex": False,
                        "includeFormulas": False,
                        "range": range_grid,  # pyright: ignore[reportArgumentType]
                    }
                }
            ],
            "includeSpreadsheetInResponse": False,
        },
    ).execute(num_retries=MAX_RETRIES)


def create_drive_data_file(data: "MediaFileUpload", metadata: "File") -> datetime:
    return datetime.strptime(
        driveService.create(  # pyright: ignore[reportTypedDictNotRequiredAccess]
            body=metadata, media_body=data, fields="modifiedTime"
        ).execute(num_retries=MAX_RETRIES)["modifiedTime"],
        "%Y-%m-%dT%H:%M:%S.%fZ",
    )


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


def update_drive_data_file(file_id: str, data: "MediaFileUpload") -> datetime:
    return datetime.strptime(
        driveService.update(  # pyright: ignore[reportTypedDictNotRequiredAccess]
            fileId=file_id, media_body=data, fields="modifiedTime"
        ).execute(num_retries=MAX_RETRIES)["modifiedTime"],
        "%Y-%m-%dT%H:%M:%S.%fZ",
    )


def decrypt_ecb(data: str | bytes) -> bytes:
    cipher_ecb = AES.new(AES_KEY, AES.MODE_ECB)
    return unpad(cipher_ecb.decrypt(b64decode(data)), AES.block_size)


def decrypt_cbc(data: str | bytes, iv: str | bytes) -> bytes:
    if isinstance(iv, str):
        iv = iv.encode()

    cipher_cbc = AES.new(AES_KEY, AES.MODE_CBC, iv)
    return unpad(cipher_cbc.decrypt(b64decode(data)), AES.block_size)


def encrypt_cbc(data: str | bytes, iv: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode()
    if isinstance(iv, str):
        iv = iv.encode()

    cipher_cbc = AES.new(AES_KEY, AES.MODE_CBC, iv)
    return b64encode(cipher_cbc.encrypt(pad(data, AES.block_size))).decode()


async def pin_new_ssl(
    embed: discord.Embed,
    pin_channel: discord.TextChannel,
) -> int:
    msg = await pin_channel.send(embed=embed)
    await asyncio.sleep(1)
    await msg.pin()
    return msg.id


async def unpin_old_ssl(
    embed_title: str | None, pin_channel: discord.TextChannel, new_pin: int
) -> None:
    if embed_title is None:
        return

    pins = await pin_channel.pins()
    for pin in pins:
        if pin.id == new_pin:
            continue

        embeds = pin.embeds
        if embeds and embeds[0].title and embed_title in embeds[0].title:
            await pin.unpin()
            break


async def get_ss_json(response: ClientResponse, iv: str | bytes) -> dict:
    try:
        result = await response.json(content_type=None)
    except json.JSONDecodeError:
        result = json.loads(decrypt_cbc(await response.text(), iv))
    return result


def get_column_letter(index: int) -> str:
    return chr((index) % 26 + ord("A"))
