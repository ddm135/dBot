from typing import TYPE_CHECKING, NotRequired, TypedDict
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from statics.consts import AssetScheme, InfoColumns


class GridRange(TypedDict, total=False):
    endColumnIndex: int
    endRowIndex: int
    sheetId: int
    startColumnIndex: int
    startRowIndex: int


class SpreadsheetDetails(TypedDict):
    spreadsheetId: str
    range: str
    columns: tuple[str, ...]
    replaceGrid: GridRange
    write: NotRequired[str]


class GameDetails(TypedDict):
    name: str
    infoSpreadsheet: str
    infoReplaceGrid: dict[str, int | str]
    infoRange: str
    infoColumns: "InfoColumns"
    pingSpreadsheet: str
    pingReplaceGrid: dict[str, int | str]
    pingRange: str
    pingUsers: str
    pingColumns: tuple[str, ...]
    bonus: NotRequired[SpreadsheetDetails]
    color: int
    pinChannelIds: dict[int, int | None]
    pinRoles: dict[int, int | None]
    dateFormat: str
    timezone: ZoneInfo
    manifest: str
    api: str
    assetScheme: "AssetScheme"
    catalog: NotRequired[str]
    authorization: NotRequired[str]
    target_audience: NotRequired[str]


class LastAppearance(TypedDict):
    songs: dict[str, str | None]
    date: str | None
