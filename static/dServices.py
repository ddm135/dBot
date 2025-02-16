import typing

from apiclient.discovery import build  # type: ignore
from Cryptodome.Cipher import AES
from google.oauth2.service_account import Credentials

from static.dConsts import A_JSON_HEADERS, AES_KEY

if typing.TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4 import SheetsResource  # type: ignore

_gCredentials = Credentials.from_service_account_file(
    filename="service_account.json",
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)
sheetService: "SheetsResource.SpreadsheetsResource.ValuesResource" = (
    build(serviceName="sheets", version="v4", credentials=_gCredentials)
    .spreadsheets()
    .values()
)

cryptServiceECB = AES.new(AES_KEY.encode(), AES.MODE_ECB)
cryptServiceCBC = AES.new(
    AES_KEY.encode(),
    AES.MODE_CBC,
    A_JSON_HEADERS["X-SuperStar-AES-IV"].encode(),
)
