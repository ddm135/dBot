import typing
from base64 import b64decode
from typing import Optional, Union

from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import unpad

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
        f"sheetService{instance or ''}"
    ]

    result = _sheetService.get(
        spreadsheetId=spreadsheet_id,
        range=range_str,
    ).execute()
    return result.get("values", [])


def update_sheet_data(
    spreadsheet_id: str,
    range_str: str,
    parse_input: bool,
    data: list[list[str]],
    instance: Optional[str] = None,
) -> None:
    _sheetService: "SheetsResource.SpreadsheetsResource.ValuesResource" = globals()[
        f"sheetService{instance or ''}"
    ]

    _sheetService.update(
        spreadsheetId=spreadsheet_id,
        range=range_str,
        valueInputOption="USER_ENTERED" if parse_input else "RAW",
        body={"values": data},
    ).execute()


def decrypt_ecb(data: Union[str, bytes]) -> bytes:
    return unpad(cryptServiceECB.decrypt(b64decode(data)), AES.block_size)


def decrypt_cbc(data: Union[str, bytes]) -> bytes:
    return unpad(cryptServiceCBC.decrypt(b64decode(data)), AES.block_size)
