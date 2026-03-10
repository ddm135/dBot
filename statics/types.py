from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, NotRequired, TypedDict
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4 import GridRange


class SpreadsheetDetails(TypedDict):
    id: str
    ranges: list[str]
    columns: list[tuple[str, ...]]
    replaceGrids: NotRequired[list["GridRange"]]


class ForwardUpdateDetails(TypedDict):
    source_maint: int
    source_msd: NotRequired[int]
    target: dict[int, int | None]


class GameDetails(TypedDict):
    name: str
    iconUrl: NotRequired[str]
    color: int
    spreadsheet: SpreadsheetDetails
    base_score: NotRequired[int]
    pinChannelIds: NotRequired[dict[int, int | None]]
    pinRoles: NotRequired[dict[int, int | None]]
    forward: NotRequired[ForwardUpdateDetails]
    dateFormat: str
    timezone: ZoneInfo
    packageName: str
    lookupQuery: NotRequired[str]
    lastVersion: NotRequired[str]
    manifestUrl: str
    catalogUrl: NotRequired[str]
    authorization: NotRequired[str]
    target_audience: NotRequired[str]


class BasicDetails(TypedDict):
    iconUrl: str
    manifest: dict[str, str]
    catalog: NotRequired[dict[str, dict[str, str]]]


class ArtistDetails(TypedDict):
    code: int
    emblem: str | Path | None
    count: int
    score: int


class LastAppearance(TypedDict):
    songs: dict[str, str | None]
    date: str | None


class LastAppearanceManual(TypedDict):
    artist: str
    songId: str
    date: str


class BonusDict(TypedDict):
    artist: str
    members: str | None
    song: str | None
    bonusStart: datetime
    bonusEnd: datetime
    bonusAmount: int
    maxScore: int
