from itertools import islice
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from statics.consts import GAMES, MAX_AUTOCOMPLETE, TIMEZONES
from statics.helpers import get_sheet_data

if TYPE_CHECKING:
    from dBot import dBot
    from statics.types import GameDetails


async def artist_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    if not (game := itr.namespace.game) or not itr.client.bonus_data_ready:
        return []

    artists = itr.client.bonus_data[game].keys()
    artist_choices = (
        app_commands.Choice(name=artist, value=artist)
        for artist in artists
        if current.lower() in artist.lower()
    )

    return list(islice(artist_choices, MAX_AUTOCOMPLETE))


def get_ping_data(
    spreadsheet_id: str, range_str: str, instance: str | None = None
) -> list[list[str]]:
    return get_sheet_data(spreadsheet_id, range_str, instance)


def _ping_preprocess(game: str) -> tuple["GameDetails", list[list[str]], int, int]:
    game_details = GAMES[game]
    ping_columns = game_details["pingColumns"]
    return (
        game_details,
        get_ping_data(
            game_details["pingId"],
            game_details["pingRange"],
            "KR" if game_details["timezone"] == TIMEZONES["KST"] else None,
        ),
        *get_ping_indexes(ping_columns),
    )


def get_ping_indexes(
    ping_columns: tuple[str, ...],
) -> tuple[int, int]:
    artist_name_index = ping_columns.index("artist_name")
    users_index = ping_columns.index("users")
    return artist_name_index, users_index
