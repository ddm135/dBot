# pyright: reportMissingModuleSource=false
# pylint: disable=no-member

from typing import TYPE_CHECKING

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from statics.consts import MAX_RETRIES

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3 import DriveResource
    from googleapiclient._apis.sheets.v4 import SheetsResource

sheetServiceDefault: "SheetsResource.SpreadsheetsResource" = build(
    serviceName="sheets",
    version="v4",
    credentials=Credentials.from_service_account_file(
        filename="dBotDefault.json",
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    ),
    num_retries=MAX_RETRIES,
    static_discovery=True,
).spreadsheets()
sheetServiceKR: "SheetsResource.SpreadsheetsResource" = build(
    serviceName="sheets",
    version="v4",
    credentials=Credentials.from_service_account_file(
        filename="dBotKR.json",
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    ),
    num_retries=MAX_RETRIES,
    static_discovery=True,
).spreadsheets()

driveService: "DriveResource.FilesResource" = build(
    serviceName="drive",
    version="v3",
    credentials=Credentials.from_service_account_file(
        filename="dBotDefault.json",
        scopes=["https://www.googleapis.com/auth/drive.file"],
    ),
    num_retries=MAX_RETRIES,
    static_discovery=True,
).files()
