import typing

from apiclient.discovery import build  # type: ignore
from Cryptodome.Cipher import AES
from google.oauth2.service_account import Credentials

if typing.TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4 import SheetsResource  # type: ignore

_gCredentials = Credentials.from_service_account_file(
    filename="service_account.json",
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)
sheetService: SheetsResource.SpreadsheetsResource.ValuesResource = (
    build(serviceName="sheets", version="v4", credentials=_gCredentials)
    .spreadsheets()
    .values()
)

cryptService = AES.new("WnFKN1v_gUcgmUVZnjjjGXGwk557zBSO".encode("utf8"), AES.MODE_ECB)
