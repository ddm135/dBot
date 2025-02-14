import discord
from discord import app_commands

from static.dConsts import GAMES, MAX_AUTOCOMPLETE_RESULTS
from static.dHelpers import get_sheet_data
from static.dTypes import GameDetails


async def artist_autocomplete(
    itr: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    game_details = GAMES[itr.namespace.game]
    ssl_data = _get_ssl_data(game_details)

    assert game_details["sslColumns"]
    artist_name_index = game_details["sslColumns"].index("artist_name")
    artists = [
        app_commands.Choice(name=artist, value=artist)
        for artist in dict.fromkeys(tuple(zip(*ssl_data))[artist_name_index])
        if current.lower() in artist.lower()
    ]

    return artists[:MAX_AUTOCOMPLETE_RESULTS]


async def song_autocomplete(
    itr: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    game_details = GAMES[itr.namespace.game]
    artist_name = itr.namespace.artist_name
    ssl_data = _get_ssl_data(game_details)

    assert game_details["sslColumns"]
    artist_name_index = game_details["sslColumns"].index("artist_name")
    song_name_index = game_details["sslColumns"].index("song_name")
    songs = [
        app_commands.Choice(name=s[song_name_index], value=s[song_name_index])
        for s in ssl_data
        if artist_name == s[artist_name_index]
        and current.lower() in s[song_name_index].lower()
    ]

    return songs[:MAX_AUTOCOMPLETE_RESULTS]


async def song_id_autocomplete(
    itr: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    game_details = GAMES[itr.namespace.game]
    ssl_data = _get_ssl_data(game_details)

    assert game_details["sslColumns"]
    artist_name_index = game_details["sslColumns"].index("artist_name")
    song_name_index = game_details["sslColumns"].index("song_name")
    song_id_index = game_details["sslColumns"].index("song_id")

    if song := next((s for s in ssl_data if current == s[song_id_index]), None):
        return [
            app_commands.Choice(
                name=f"{song[artist_name_index]} - {song[song_name_index]}",
                value=song[song_id_index],
            )
        ]
    return []


def _get_ssl_data(game_details: GameDetails) -> list[list[str]]:
    assert game_details["sslId"]
    assert game_details["sslRange"]
    return get_sheet_data(game_details["sslId"], game_details["sslRange"])
