from typing import TYPE_CHECKING, NotRequired, TypedDict
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4 import GridRange

    from statics.consts import AssetScheme


class SpreadsheetDetails(TypedDict):
    spreadsheetId: str
    range: str
    columns: tuple[str, ...]
    replaceGrid: "GridRange"


class ForwardUpdateDetails(TypedDict):
    source_maint: int
    source_msd: NotRequired[int]
    target: dict[int, int | None]


class GameDetails(TypedDict):
    name: str
    iconUrl: NotRequired[str]
    color: int
    info: NotRequired[SpreadsheetDetails]
    bonus: NotRequired[SpreadsheetDetails]
    ping: NotRequired[SpreadsheetDetails]
    emblem: SpreadsheetDetails
    pinChannelIds: dict[int, int | None]
    pinRoles: dict[int, int | None]
    forward: NotRequired[ForwardUpdateDetails]
    dateFormat: str
    timezone: ZoneInfo
    lookupQuery: NotRequired[str]
    manifestUrl: NotRequired[str]
    packageName: str
    assetScheme: "AssetScheme"
    catalogUrl: NotRequired[str]
    authorization: NotRequired[str]
    target_audience: NotRequired[str]


class CatalogDetails(TypedDict):
    internalId: str
    dependency: str | None


class BasicDetails(TypedDict):
    version: str
    iconUrl: str
    manifest: dict[str, str]
    catalog: NotRequired[dict[str, CatalogDetails]]


class LastAppearance(TypedDict):
    songs: dict[str, str | None]
    date: str | None


class LastAppearanceManual(TypedDict):
    artist: str
    songId: str
    date: str
