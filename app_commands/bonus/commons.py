from typing import TYPE_CHECKING

from statics.consts import GAMES, TIMEZONES

if TYPE_CHECKING:
    from dBot import dBot
    from statics.types import GameDetails


STEP = 5


async def ping_preprocess(
    game: str, bot: "dBot"
) -> tuple["GameDetails", list[list[str]], int, int]:
    game_details = GAMES[game]
    ping_columns = game_details["pingColumns"]
    cog = bot.get_cog("GoogleSheets")
    return (
        game_details,
        await cog.get_sheet_data(  # type: ignore[union-attr]
            game_details["pingSpreadsheet"],
            game_details["pingRange"],
            "kr" if game_details["timezone"] == TIMEZONES["KST"] else None,
        ),
        ping_columns.index("artist_name"),
        ping_columns.index("users"),
    )
