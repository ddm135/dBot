import itertools
from typing import Optional, Union

import discord
from discord import app_commands

from static.dConsts import GAMES, MAX_AUTOCOMPLETE_RESULTS, TIMEZONES
from static.dHelpers import get_column_letter, get_sheet_data, update_sheet_data
from static.dTypes import GameDetails


async def artist_autocomplete(
    itr: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    if not itr.namespace.game:
        return []
    game_details = GAMES[itr.namespace.game]

    assert (ssl_id := game_details["sslId"])
    assert (ssl_artist_range := game_details["sslArtists"])
    ssl_artists = get_sheet_data(
        ssl_id,
        ssl_artist_range,
        "KR" if game_details["timezone"] == TIMEZONES["KST"] else None,
    )

    artists = [
        app_commands.Choice(name=artist, value=artist)
        for artist in itertools.chain.from_iterable(ssl_artists)
        if current.lower() in artist.lower()
    ]

    return artists[:MAX_AUTOCOMPLETE_RESULTS]


async def song_autocomplete(
    itr: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    artist_name: str = itr.namespace.artist_name
    (
        game_details,
        artist_name_index,
        song_name_index,
        _,
        _,
        _,
        search_term_index,
        _,
    ) = _ssl_preprocess(itr.namespace.game)

    assert (ssl_full_range := game_details["sslSongs"])
    filter = (
        (
            f'=QUERY({ssl_full_range}, "SELECT * WHERE LOWER('
            f'{get_column_letter(artist_name_index)}) = ""{artist_name}"" '
            f"AND (LOWER({get_column_letter(song_name_index)}) "
            f'CONTAINS LOWER(""{current}"") OR '
            f"LOWER({get_column_letter(search_term_index)}) "
            f'CONTAINS LOWER(""{current}""))", 0)'
        )
        if current
        else (
            f'=QUERY({ssl_full_range}, "SELECT * WHERE LOWER('
            f"{get_column_letter(artist_name_index)}) "
            f'= ""{artist_name}""", 0)'
        )
    )
    _update_ssl_filter(game_details, filter)

    ssl_songs = _get_ssl_data(game_details)
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
    itr: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    (
        game_details,
        artist_name_index,
        song_name_index,
        song_id_index,
        _,
        _,
        _,
        _,
    ) = _ssl_preprocess(itr.namespace.game)

    assert (ssl_full_range := game_details["sslSongs"])
    filter = (
        f'=QUERY({ssl_full_range}, "SELECT * WHERE '
        f"{get_column_letter(song_id_index)} = {current}, 0)"
    )
    _update_ssl_filter(game_details, filter)

    ssl_songs = _get_ssl_data(game_details)
    if not ssl_songs:
        return []

    if song := next((s for s in ssl_songs if current == s[song_id_index]), None):
        return [
            app_commands.Choice(
                name=f"{song[artist_name_index]} - {song[song_name_index]}",
                value=song[song_id_index],
            )
        ]
    return []


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
    assert (ssl_columns := game_details["sslColumns"])
    return game_details, *_get_ssl_indexes(ssl_columns)


def _get_ssl_data(game_details: GameDetails) -> list[list[str]]:
    assert (ssl_id := game_details["sslId"])
    assert (ssl_filtered_range := game_details["sslFiltereds"])
    return get_ssl_data(
        ssl_id,
        ssl_filtered_range,
        "KR" if game_details["timezone"] == TIMEZONES["KST"] else None,
    )


def _update_ssl_filter(game_details: GameDetails, filter: str) -> None:
    assert (ssl_id := game_details["sslId"])
    assert (ssl_filtered_range := game_details["sslFiltereds"])
    update_ssl_filter(
        ssl_id,
        ssl_filtered_range,
        data=[[filter]],
    )


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
