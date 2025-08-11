from itertools import islice
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from statics.consts import MAX_AUTOCOMPLETE

if TYPE_CHECKING:
    from dBot import dBot


async def artist_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    if not (game := itr.namespace.game):
        return []

    artists = itr.client.bonus[game].keys()
    artist_choices = (
        app_commands.Choice(name=artist, value=artist)
        for artist in artists
        if current.lower() in artist.lower()
    )

    return list(islice(artist_choices, MAX_AUTOCOMPLETE))
