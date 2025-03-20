import typing
from base64 import b64decode
from typing import Optional, Union

from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import unpad

from static.dConsts import AES_IV, MAX_RETRIES
from static.dServices import (  # noqa: F401
    cryptServiceCBC,
    cryptServiceECB,
    sheetService,
    sheetServiceKR,
)

if typing.TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4 import SheetsResource  # type: ignore


def get_sheet_data(
    spreadsheet_id: str,
    range_str: str,
    instance: Optional[str] = None,
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
    instance: Optional[str] = None,
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
    instance: Optional[str] = None,
) -> None:
    _sheetService: "SheetsResource.SpreadsheetsResource.ValuesResource" = globals()[
        f"sheetService{instance or ""}"
    ]

    _sheetService.clear(
        spreadsheetId=spreadsheet_id,
        range=range_str,
        body={},
    ).execute(num_retries=MAX_RETRIES)


def decrypt_ecb(data: Union[str, bytes]) -> bytes:
    return unpad(cryptServiceECB.decrypt(b64decode(data)), AES.block_size)


def decrypt_cbc(data: Union[str, bytes]) -> bytes:
    cryptServiceCBC.iv = AES_IV.encode()
    return unpad(cryptServiceCBC.decrypt(b64decode(data)), AES.block_size)
