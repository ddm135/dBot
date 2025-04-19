from base64 import b64decode, b64encode
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad, unpad
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from statics.consts import AES_IV, AES_KEY, MAX_RETRIES
from statics.services import driveService, sheetService, sheetServiceKR  # noqa: F401

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3 import File, FileList  # type: ignore
    from googleapiclient._apis.sheets.v4 import SheetsResource  # type: ignore


def get_sheet_data(
    spreadsheet_id: str,
    range_str: str,
    instance: str | None = None,
) -> list[list[str]]:
    _sheetService: "SheetsResource.SpreadsheetsResource.ValuesResource" = globals()[
        f"sheetService{instance or ""}"
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
        f"sheetService{instance or ""}"
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
        f"sheetService{instance or ""}"
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


def get_drive_data_file(file_id: str, path: Path) -> None:
    request = driveService.get_media(fileId=file_id)
    file = BytesIO()
    downloader = MediaIoBaseDownload(file, request)
    done = False
    while done is False:
        _, done = downloader.next_chunk(num_retries=MAX_RETRIES)

    with open(path, "wb") as f:
        f.write(file.getbuffer())
    file.close()


def update_drive_data_file(file_id: str, data: "MediaFileUpload") -> None:
    driveService.update(
        fileId=file_id,
        media_body=data,
    ).execute(num_retries=MAX_RETRIES)


def decrypt_ecb(data: str | bytes) -> bytes:
    cipherECB = AES.new(AES_KEY.encode(), AES.MODE_ECB)
    return unpad(cipherECB.decrypt(b64decode(data)), AES.block_size)


def decrypt_cbc(data: str | bytes) -> bytes:
    cipherCBC = AES.new(AES_KEY.encode(), AES.MODE_CBC, AES_IV.encode())
    return unpad(cipherCBC.decrypt(b64decode(data)), AES.block_size)


def encrypt_cbc(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()

    cipherCBC = AES.new(
        AES_KEY.encode(),
        AES.MODE_CBC,
        AES_IV.encode(),
    )
    return b64encode(cipherCBC.encrypt(pad(data, AES.block_size))).decode()


def get_column_letter(index: int) -> str:
    return chr((index) % 26 + ord("A"))
