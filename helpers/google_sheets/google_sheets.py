# mypy: disable-error-code="attr-defined"
# pylint: disable=no-member
# pyright: reportAttributeAccessIssue=false

import asyncio
from typing import TYPE_CHECKING

from discord.ext import commands
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from statics.consts import MAX_RETRIES

from .commons import SCOPES, SERVICE_NAME, STATIC_DISCOVERY, VERSION

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4 import SheetsResource

    from dBot import dBot
    from statics.types import GridRange


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

    async def get_sheet_data(
        self,
        spreadsheet_id: str,
        range_str: str,
        instance: str | None = None,
    ) -> list[list[str]]:
        service: "SheetsResource.SpreadsheetsResource" = getattr(
            self,
            instance or "default",
        )
        result = await asyncio.to_thread(
            service.values()
            .get(
                spreadsheetId=spreadsheet_id,
                range=range_str,
            )
            .execute,
            num_retries=MAX_RETRIES,
        )
        return result.get("values", [])

    async def update_sheet_data(
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
        await asyncio.to_thread(
            service.values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=range_str,
                valueInputOption="RAW",
                body={"values": data},
            )
            .execute,
            num_retries=MAX_RETRIES,
        )

    async def find_replace_sheet_data(
        self,
        spreadsheet_id: str,
        range_grid: "GridRange",
        find: str,
        replace: str,
        instance: str | None = None,
    ) -> None:
        service: "SheetsResource.SpreadsheetsResource" = getattr(
            self,
            instance or "default",
        )
        await asyncio.to_thread(
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
                                "range": range_grid,
                            }
                        }
                    ],
                    "includeSpreadsheetInResponse": False,
                },
            ).execute,
            num_retries=MAX_RETRIES,
        )


async def setup(bot: "dBot") -> None:
    await bot.add_cog(GoogleSheets())
