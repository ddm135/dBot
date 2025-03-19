import typing

from apiclient.discovery import build  # type: ignore
from Cryptodome.Cipher import AES
from google.oauth2.service_account import Credentials

from static.dConsts import AES_IV, AES_KEY

if typing.TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4 import SheetsResource  # type: ignore

_gCredentials = Credentials.from_service_account_file(
    filename="dBotDefault.json",
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)
sheetService: "SheetsResource.SpreadsheetsResource.ValuesResource" = (
    build(serviceName="sheets", version="v4", credentials=_gCredentials)
    .spreadsheets()
    .values()
)
_gCredentialsKR = Credentials.from_service_account_file(
    filename="dBotKR.json",
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)
sheetServiceKR: "SheetsResource.SpreadsheetsResource.ValuesResource" = (
    build(serviceName="sheets", version="v4", credentials=_gCredentialsKR)
    .spreadsheets()
    .values()
)

cryptServiceECB = AES.new(AES_KEY.encode(), AES.MODE_ECB)
cryptServiceCBC = AES.new(
    AES_KEY.encode(),
    AES.MODE_CBC,
    AES_IV.encode(),
)
