from typing import TypedDict


class SSLD(TypedDict):
    spreadsheetId: str
    spreadsheetRange: str
    spreadsheetColumns: list[str]
    pinChannelId: int
    timezone: str
    api: str


class BonusD(TypedDict):
    name: str
    pingId: str
    pingRange: str
    pingWrite: str
    pingColumns: list[str]
    bonusId: str
    bonusRange: str
    bonusColumns: list[str]
    timezone: str
