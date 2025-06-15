from enum import Enum
from typing import TYPE_CHECKING

from statics.consts import GAMES, TIMEZONES
from statics.helpers import get_sheet_data

if TYPE_CHECKING:
    from statics.types import GameDetails


STEP = 5


BonusPeriod = Enum(
    "BonusPeriod", [("current week", 1), ("next week", 2), ("current month", 3)]
)


def get_ping_data(
    spreadsheet_id: str, range_str: str, instance: str | None = None
) -> list[list[str]]:
    return get_sheet_data(spreadsheet_id, range_str, instance)


def ping_preprocess(game: str) -> tuple["GameDetails", list[list[str]], int, int]:
    game_details = GAMES[game]
    ping_columns = game_details["pingColumns"]
    return (
        game_details,
        get_ping_data(
            game_details["pingSpreadsheet"],
            game_details["pingRange"],
            "KR" if game_details["timezone"] == TIMEZONES["KST"] else None,
        ),
        ping_columns.index("artist_name"),
        ping_columns.index("users"),
    )
