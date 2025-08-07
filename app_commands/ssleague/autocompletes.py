from itertools import islice
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from statics.consts import GAMES, MAX_AUTOCOMPLETE

if TYPE_CHECKING:
    from dBot import dBot


async def artist_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    if not (game := itr.namespace.game) or not itr.client.info_ready:
        return []

    artists = itr.client.info_by_name[game].keys()
    artist_choices = (
        app_commands.Choice(name=artist, value=artist)
        for artist in artists
        if current.lower() in artist.lower()
    )

    return list(islice(artist_choices, MAX_AUTOCOMPLETE))


async def song_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    if not (game := itr.namespace.game) or not itr.client.info_ready:
        return []

    search_term_index = GAMES[game]["infoColumns"].index("search_term")
    songs = itr.client.info_by_name[game][itr.namespace.artist]
    if not songs:
        return []

    song_choices = (
        app_commands.Choice(name=song_name, value=song_name)
        for song_name, song_details in songs.items()
        if current.lower() in song_name.lower()
        or current.lower() in song_details[search_term_index].lower()
    )

    return list(islice(song_choices, MAX_AUTOCOMPLETE))


async def song_id_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    if not (game := itr.namespace.game) or not itr.client.info_ready:
        return []
    info_columns = GAMES[game]["infoColumns"]
    artist_name_index = info_columns.value.index("artist_name")
    song_name_index = info_columns.value.index("song_name")

    song = itr.client.info_by_id[game][current]
    if not song:
        return []

    return [
        app_commands.Choice(
            name=f"{song[artist_name_index]} - {song[song_name_index]}",
            value=current,
        )
    ]
