# pyright: reportMissingModuleSource = false

from typing import TYPE_CHECKING

from apiclient.discovery import build
from google.oauth2.service_account import Credentials

from statics.consts import MAX_RETRIES

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4 import SheetsResource

_gCredentials = Credentials.from_service_account_file(
    filename="dBotDefault.json",
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)
sheetService: "SheetsResource.SpreadsheetsResource.ValuesResource" = (
    build(
        serviceName="sheets",
        version="v4",
        credentials=_gCredentials,
        num_retries=MAX_RETRIES,
        static_discovery=True,
    )
    .spreadsheets()
    .values()
)
_gCredentialsKR = Credentials.from_service_account_file(
    filename="dBotKR.json",
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)
sheetServiceKR: "SheetsResource.SpreadsheetsResource.ValuesResource" = (
    build(
        serviceName="sheets",
        version="v4",
        credentials=_gCredentialsKR,
        num_retries=MAX_RETRIES,
        static_discovery=True,
    )
    .spreadsheets()
    .values()
)
