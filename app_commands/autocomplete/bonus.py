from itertools import islice

import discord
from discord import app_commands

from static.dConsts import GAMES, MAX_AUTOCOMPLETE_RESULTS
from static.dServices import sheetService


async def artist_autocomplete(
    itr: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    game_details = GAMES[itr.namespace.game]
    result = (
        sheetService.values()
        .get(
            spreadsheetId=game_details["pingId"],
            range=game_details["pingRange"],
        )
        .execute()
    )
    values = result.get("values", [])

    artist_column_index = game_details["pingColumns"].index("artist_name")
    artists = list(dict.fromkeys(list(zip(*values))[artist_column_index]))
    filtered_artists = [
        app_commands.Choice(name=artist, value=artist)
        for artist in artists
        if current.lower() in artist.lower()
    ]

    return list(islice(filtered_artists, MAX_AUTOCOMPLETE_RESULTS))
