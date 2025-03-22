from typing import TYPE_CHECKING

import discord
from discord import app_commands

from static.dConsts import GAMES, MAX_AUTOCOMPLETE_RESULTS, TIMEZONES
from static.dHelpers import get_sheet_data

if TYPE_CHECKING:
    from dBot import dBot
    from static.dTypes import GameDetails


async def artist_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    _, ping_data, artist_name_index, _ = _ping_preprocess(itr.namespace.game)

    artists = [
        app_commands.Choice(name=artist, value=artist)
        for artist in dict.fromkeys(tuple(zip(*ping_data))[artist_name_index])
        if current.lower() in artist.lower()
    ]

    return artists[:MAX_AUTOCOMPLETE_RESULTS]


def get_ping_data(
    spreadsheet_id: str, range_str: str, instance: str | None = None
) -> list[list[str]]:
    return get_sheet_data(spreadsheet_id, range_str, instance)


def _ping_preprocess(game: str) -> tuple["GameDetails", list[list[str]], int, int]:
    game_details = GAMES[game]
    ping_data = _get_ping_data(game_details)
    ping_columns = game_details["pingColumns"]
    return game_details, ping_data, *_get_ping_indexes(ping_columns)


def _get_ping_data(game_details: "GameDetails") -> list[list[str]]:
    return get_ping_data(
        game_details["pingId"],
        game_details["pingRange"],
        "KR" if game_details["timezone"] == TIMEZONES["KST"] else None,
    )


def _get_ping_indexes(
    ping_columns: tuple[str, ...],
) -> tuple[int, int]:
    artist_name_index = ping_columns.index("artist_name")
    users_index = ping_columns.index("users")
    return artist_name_index, users_index
