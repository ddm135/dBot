# pyright: reportMissingModuleSource = false

from base64 import b64decode
from typing import TYPE_CHECKING

from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import unpad

from static.dConsts import AES_IV, AES_KEY, MAX_RETRIES
from static.dServices import sheetService, sheetServiceKR  # noqa: F401

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4 import SheetsResource


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


def decrypt_ecb(data: str | bytes) -> bytes:
    cipherECB = AES.new(AES_KEY.encode(), AES.MODE_ECB)
    return unpad(cipherECB.decrypt(b64decode(data)), AES.block_size)


def decrypt_cbc(data: str | bytes) -> bytes:
    cipherCBC = AES.new(AES_KEY.encode(), AES.MODE_CBC, AES_IV.encode())
    return unpad(cipherCBC.decrypt(b64decode(data)), AES.block_size)


def get_column_letter(index: int) -> str:
    return chr((index) % 26 + ord("A"))


def jsondict_str2int(x: dict[str, str]) -> dict[int, int]:
    return {int(k): int(v) for k, v in x.items()}
