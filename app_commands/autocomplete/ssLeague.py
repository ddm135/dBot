from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands

from static.dConsts import GAMES, MAX_AUTOCOMPLETE_RESULTS
from static.dHelpers import get_sheet_data, update_sheet_data

if TYPE_CHECKING:
    from dBot import dBot


async def artist_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    if not (game := itr.namespace.game) or not itr.client.info_data_ready:
        return []
    ssl_artists = itr.client.info_by_name[game].keys()

    artists = [
        app_commands.Choice(name=artist, value=artist)
        for artist in ssl_artists
        if current.lower() in artist.lower()
    ]

    return artists[:MAX_AUTOCOMPLETE_RESULTS]


async def song_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    if not (game := itr.namespace.game) or not itr.client.info_data_ready:
        return []
    ssl_columns = GAMES[game]["infoColumns"]
    artist_name: str = itr.namespace.artist
    search_term_index = ssl_columns.index("search_term")

    ssl_songs = itr.client.info_by_name[game][artist_name]
    if not ssl_songs:
        return []

    songs = [
        app_commands.Choice(name=song_name, value=song_name)
        for song_name, song_details in ssl_songs.items()
        if current.lower() in song_name.lower()
        or current.lower() in song_details[search_term_index].lower()
    ]

    return songs[:MAX_AUTOCOMPLETE_RESULTS]


async def song_id_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    if not (game := itr.namespace.game) or not itr.client.info_data_ready:
        return []
    ssl_columns = GAMES[game]["infoColumns"]
    artist_name_index = ssl_columns.index("artist_name")
    song_name_index = ssl_columns.index("song_name")

    ssl_song = itr.client.info_by_id[game][current]
    if not ssl_song:
        return []

    return [
        app_commands.Choice(
            name=f"{ssl_song[artist_name_index]} - {ssl_song[song_name_index]}",
            value=current,
        )
    ]


def get_ssl_data(
    spreadsheet_id: str, range_str: str, instance: Optional[str] = None
) -> list[list[str]]:
    return get_sheet_data(spreadsheet_id, range_str, instance)


def update_ssl_filter(
    spreadsheet_id: str,
    range_str: str,
    data: list[list[str]],
    instance: Optional[str] = None,
) -> None:
    return update_sheet_data(spreadsheet_id, range_str, True, data, instance)
