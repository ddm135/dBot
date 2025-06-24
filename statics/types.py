from typing import TypedDict
from zoneinfo import ZoneInfo


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
    authorization: str
    target_audience: str
    legacyUrlScheme: bool


class LastAppearance(TypedDict):
    songs: dict[str, str | None]
    date: str | None
