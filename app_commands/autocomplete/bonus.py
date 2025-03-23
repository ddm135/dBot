from itertools import islice
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from static.dConsts import MAX_AUTOCOMPLETE, TIMEZONES
from static.dHelpers import get_sheet_data

if TYPE_CHECKING:
    from dBot import dBot
    from static.dTypes import GameDetails


async def game_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    if not itr.client.info_data_ready:
        return []
    ssl_games = itr.client.games

    games = (
        app_commands.Choice(name=game["name"], value=key)
        for key, game in ssl_games.items()
        if game["pinChannelIds"] and current.lower() in game["name"].lower()
    )

    return list(islice(games, MAX_AUTOCOMPLETE))


async def artist_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    _, ping_data, artist_name_index, _ = _ping_preprocess(itr)

    artists = (
        app_commands.Choice(name=artist, value=artist)
        for artist in dict.fromkeys(tuple(zip(*ping_data))[artist_name_index])
        if current.lower() in artist.lower()
    )

    return list(islice(artists, MAX_AUTOCOMPLETE))


def get_ping_data(
    spreadsheet_id: str, range_str: str, instance: str | None = None
) -> list[list[str]]:
    return get_sheet_data(spreadsheet_id, range_str, instance)


def _ping_preprocess(
    itr: discord.Interaction["dBot"],
) -> tuple["GameDetails", list[list[str]], int, int]:
    game_details = itr.client.games[itr.namespace.game]
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
