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
    from dBot import dBot
    from statics.types import GridRange


class GoogleSheets(commands.Cog):
    def __init__(self) -> None:
        self.service = build(
            serviceName=SERVICE_NAME,
            version=VERSION,
            credentials=Credentials.from_service_account_file(
                filename="dBot.json",
                scopes=SCOPES,
            ),
            num_retries=MAX_RETRIES,
            static_discovery=STATIC_DISCOVERY,
        ).spreadsheets()

    async def get_sheet_data(
        self, spreadsheet_id: str, range_str: str
    ) -> list[list[str]]:
        result = await asyncio.to_thread(
            self.service.values()
            .get(
                spreadsheetId=spreadsheet_id,
                range=range_str,
            )
            .execute,
            num_retries=MAX_RETRIES,
        )
        return result.get("values", [])

    async def update_sheet_data(
        self, spreadsheet_id: str, range_str: str, data: list[list[str]]
    ) -> None:
        await asyncio.to_thread(
            self.service.values()
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
        self, spreadsheet_id: str, range_grid: "GridRange", find: str, replace: str
    ) -> None:
        await asyncio.to_thread(
            self.service.batchUpdate(
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
