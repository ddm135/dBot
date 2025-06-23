# mypy: disable-error-code="attr-defined"
# pylint: disable=no-member
# pyright: reportMissingModuleSource=false

from typing import TYPE_CHECKING

from discord.ext import commands
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from statics.consts import MAX_RETRIES

from .commons import SCOPES, SERVICE_NAME, STATIC_DISCOVERY, VERSION

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4 import SheetsResource

    from dBot import dBot


class GoogleSheets(commands.Cog):
    def __init__(self) -> None:
        self.default = build(
            serviceName=SERVICE_NAME,
            version=VERSION,
            credentials=Credentials.from_service_account_file(
                filename="dBotDefault.json",
                scopes=SCOPES,
            ),
            num_retries=MAX_RETRIES,
            static_discovery=STATIC_DISCOVERY,
        ).spreadsheets()
        self.kr = build(
            serviceName=SERVICE_NAME,
            version=VERSION,
            credentials=Credentials.from_service_account_file(
                filename="dBotKR.json",
                scopes=SCOPES,
            ),
            num_retries=MAX_RETRIES,
            static_discovery=STATIC_DISCOVERY,
        ).spreadsheets()

    def get_sheet_data(
        self,
        spreadsheet_id: str,
        range_str: str,
        instance: str | None = None,
    ) -> list[list[str]]:
        service: "SheetsResource.SpreadsheetsResource" = getattr(
            self,
            instance or "default",
        )
        return (
            service.values()
            .get(
                spreadsheetId=spreadsheet_id,
                range=range_str,
            )
            .execute(num_retries=MAX_RETRIES)
            .get("values", [])
        )

    def update_sheet_data(
        self,
        spreadsheet_id: str,
        range_str: str,
        data: list[list[str]],
        instance: str | None = None,
    ) -> None:
        service: "SheetsResource.SpreadsheetsResource" = getattr(
            self,
            instance or "default",
        )
        service.values().update(
            spreadsheetId=spreadsheet_id,
            range=range_str,
            valueInputOption="RAW",
            body={"values": data},
        ).execute(num_retries=MAX_RETRIES)

    def find_replace_sheet_data(
        self,
        spreadsheet_id: str,
        range_grid: dict[str, int | str],
        find: str,
        replace: str,
        instance: str | None = None,
    ) -> None:
        service: "SheetsResource.SpreadsheetsResource" = getattr(
            self,
            instance or "default",
        )
        service.batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [
                    {
                        "findReplace": {
                            "find": find,
                            "replacement": replace,
                            "matchCase": True,
                            "matchEntireCell": True,
                            "searchByRegex": False,
                            "includeFormulas": False,
                            "range": range_grid,  # type: ignore[typeddict-item]
                        }
                    }
                ],
                "includeSpreadsheetInResponse": False,
            },
        ).execute(num_retries=MAX_RETRIES)


async def setup(bot: "dBot") -> None:
    await bot.add_cog(GoogleSheets())
