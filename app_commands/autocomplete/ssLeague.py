from itertools import islice
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from static.dConsts import MAX_AUTOCOMPLETE

if TYPE_CHECKING:
    from dBot import dBot


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


async def _game_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    if not itr.client.info_data_ready:
        return []
    ssl_games = itr.client.games

    games = (
        app_commands.Choice(name=game["name"], value=key)
        for key, game in ssl_games.items()
        if game["pinChannelIds"]
        and current.lower() in game["name"].lower()
        and "song_id" in game["infoColumns"]
    )

    return list(islice(games, MAX_AUTOCOMPLETE))


async def artist_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    if not (game := itr.namespace.game) or not itr.client.info_data_ready:
        return []
    ssl_artists = itr.client.info_by_name[game].keys()

    artists = (
        app_commands.Choice(name=artist, value=artist)
        for artist in ssl_artists
        if current.lower() in artist.lower()
    )

    return list(islice(artists, MAX_AUTOCOMPLETE))


async def song_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    if not (game := itr.namespace.game) or not itr.client.info_data_ready:
        return []
    search_term_index = itr.client.games[game]["infoColumns"].index("search_term")

    ssl_songs = itr.client.info_by_name[game][itr.namespace.artist]
    if not ssl_songs:
        return []

    songs = (
        app_commands.Choice(name=song_name, value=song_name)
        for song_name, song_details in ssl_songs.items()
        if current.lower() in song_name.lower()
        or current.lower() in song_details[search_term_index].lower()
    )

    return list(islice(songs, MAX_AUTOCOMPLETE))


async def song_id_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    if not (game := itr.namespace.game) or not itr.client.info_data_ready:
        return []
    ssl_columns = itr.client.games[game]["infoColumns"]
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
