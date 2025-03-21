from typing import TYPE_CHECKING, Optional, Union

import discord
from discord import app_commands

from static.dConsts import GAMES, MAX_AUTOCOMPLETE_RESULTS
from static.dHelpers import get_sheet_data, update_sheet_data
from static.dTypes import GameDetails

if TYPE_CHECKING:
    from dBot import dBot


async def artist_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    if not itr.namespace.game or not itr.client.info_data_ready:
        return []
    ssl_artists = itr.client.info_by_name[itr.namespace.game].keys()

    artists = [
        app_commands.Choice(name=artist, value=artist)
        for artist in ssl_artists
        if current.lower() in artist.lower()
    ]

    return artists[:MAX_AUTOCOMPLETE_RESULTS]


async def song_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    if not itr.namespace.game or not itr.client.info_data_ready:
        return []
    artist_name: str = itr.namespace.artist_name
    (
        _,
        artist_name_index,
        song_name_index,
        _,
        _,
        _,
        search_term_index,
        _,
    ) = _ssl_preprocess(itr.namespace.game)

    ssl_songs = itr.client.info_by_name[itr.namespace.game][artist_name]
    if not ssl_songs:
        return []

    songs = [
        app_commands.Choice(name=s[song_name_index], value=s[song_name_index])
        for s in ssl_songs
        if artist_name.lower() == s[artist_name_index].lower()
        and (
            current.lower() in s[song_name_index].lower()
            or current.lower() in s[search_term_index].lower()
        )
    ]

    return songs[:MAX_AUTOCOMPLETE_RESULTS]


async def song_id_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    if not itr.namespace.game or not itr.client.info_data_ready:
        return []
    (
        _,
        artist_name_index,
        song_name_index,
        song_id_index,
        _,
        _,
        _,
        _,
    ) = _ssl_preprocess(itr.namespace.game)

    ssl_song = itr.client.info_by_id[itr.namespace.game][current]
    if not ssl_song:
        return []

    return [
        app_commands.Choice(
            name=f"{ssl_song[artist_name_index]} - {ssl_song[song_name_index]}",
            value=ssl_song[song_id_index],
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


def _ssl_preprocess(
    game: str,
) -> tuple[GameDetails, int, int, int, int, int, int, Optional[int]]:
    game_details = GAMES[game]
    return game_details, *_get_ssl_indexes(game_details["infoColumns"])


def _get_ssl_indexes(
    ssl_columns: Union[list[str], tuple[str, ...]],
) -> tuple[int, int, int, int, int, int, Optional[int]]:
    song_id_index = ssl_columns.index("song_id")
    artist_name_index = ssl_columns.index("artist_name")
    song_name_index = ssl_columns.index("song_name")
    duration_index = ssl_columns.index("duration")
    image_url_index = ssl_columns.index("image")
    search_term_index = ssl_columns.index("search_term")
    skills_index = ssl_columns.index("skills") if "skills" in ssl_columns else None
    return (
        artist_name_index,
        song_name_index,
        song_id_index,
        duration_index,
        image_url_index,
        search_term_index,
        skills_index,
    )
