from typing import TYPE_CHECKING, NotRequired, TypedDict
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from statics.consts import AssetScheme


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


class GameDetails(TypedDict):
    name: str
    color: int
    info: NotRequired[SpreadsheetDetails]
    bonus: NotRequired[SpreadsheetDetails]
    ping: NotRequired[SpreadsheetDetails]
    emblem: NotRequired[SpreadsheetDetails]
    pinChannelIds: dict[int, int | None]
    pinRoles: dict[int, int | None]
    dateFormat: str
    timezone: ZoneInfo
    lookupQuery: NotRequired[str]
    manifestUrl: NotRequired[str]
    assetScheme: "AssetScheme"
    catalogUrl: NotRequired[str]
    authorization: NotRequired[str]
    target_audience: NotRequired[str]


class BasicDetails(TypedDict):
    version: str
    manifest: dict[str, str]
    catalog: NotRequired[dict[str, dict[str, str]]]


class LastAppearance(TypedDict):
    songs: dict[str, str | None]
    date: str | None
