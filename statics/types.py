from typing import TypedDict
from zoneinfo import ZoneInfo

from statics.consts import AssetScheme


class GameDetails(TypedDict):
    name: str
    infoSpreadsheet: str
    infoReplaceGrid: dict[str, int | str]
    infoRange: str
    infoColumns: tuple[str, ...]
    pingSpreadsheet: str
    pingReplaceGrid: dict[str, int | str]
    pingRange: str
    pingUsers: str
    pingColumns: tuple[str, ...]
    bonusSpreadsheet: str
    bonusReplaceGrid: dict[str, int | str]
    bonusRange: str
    bonusColumns: tuple[str, ...]
    color: int
    pinChannelIds: dict[int, int | None]
    pinRoles: dict[int, int | None]
    dateFormat: str
    timezone: ZoneInfo
    manifest: str
    api: str
    assetScheme: AssetScheme
    catalog: str
    authorization: str
    target_audience: str


class LastAppearance(TypedDict):
    songs: dict[str, str | None]
    date: str | None
