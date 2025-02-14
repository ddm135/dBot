from base64 import b64decode
from typing import Union

from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import unpad

from static.dServices import cryptServiceCBC, cryptServiceECB, sheetService


def get_sheet_data(spreadsheet_id: str, range_str: str) -> list[list[str]]:
    result = sheetService.get(
        spreadsheetId=spreadsheet_id,
        range=range_str,
    ).execute()
    return result.get("values", [])


def update_sheet_data(
    spreadsheet_id: str,
    range_str: str,
    parse_input: bool,
    data: list[list[str]],
) -> None:
    sheetService.update(
        spreadsheetId=spreadsheet_id,
        range=range_str,
        valueInputOption="USER_ENTERED" if parse_input else "RAW",
        body={"values": data},
    ).execute()


def decrypt_ecb(data: Union[str, bytes]) -> bytes:
    return unpad(cryptServiceECB.decrypt(b64decode(data)), AES.block_size)


def decrypt_cbc(data: Union[str, bytes]) -> bytes:
    return unpad(cryptServiceCBC.decrypt(b64decode(data)), AES.block_size)
