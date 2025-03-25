from typing import TYPE_CHECKING

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from statics.consts import MAX_RETRIES

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3 import DriveResource  # type: ignore
    from googleapiclient._apis.sheets.v4 import SheetsResource  # type: ignore

_gCredentials = Credentials.from_service_account_file(
    filename="dBotDefault.json",
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
    ],
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
driveService: "DriveResource.FilesResource" = build(
    serviceName="drive",
    version="v3",
    credentials=_gCredentials,
    num_retries=MAX_RETRIES,
    static_discovery=True,
).files()

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
