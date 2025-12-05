# pyright: reportTypedDictNotRequiredAccess=false

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
    if not (game := itr.namespace.game):
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
    if not (game := itr.namespace.game):
        return []

    # search_term_index = GAMES[game]["info"]["columns"].index("search_term")
    if not (songs := itr.client.info_by_name[game].get(itr.namespace.artist, {})):
        return []

    song_choices = (
        app_commands.Choice(name=song_name, value=song_name)
        for song_name, song_details in songs.items()
        if current.lower() in song_name.lower()
        # or current.lower() in song_details[search_term_index].lower()
    )

    return list(islice(song_choices, MAX_AUTOCOMPLETE))
