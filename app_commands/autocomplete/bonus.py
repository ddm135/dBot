import discord
from discord import app_commands

from static.dConsts import GAMES, MAX_AUTOCOMPLETE_RESULTS
from static.dHelpers import get_sheet_data
from static.dTypes import GameDetails


async def artist_autocomplete(
    itr: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    game_details = GAMES[itr.namespace.game]
    ping_data = _get_ping_data(game_details)

    artist_column_index = game_details["pingColumns"].index("artist_name")
    artists = [
        app_commands.Choice(name=artist, value=artist)
        for artist in dict.fromkeys(tuple(zip(*ping_data))[artist_column_index])
        if current.lower() in artist.lower()
    ]

    return artists[:MAX_AUTOCOMPLETE_RESULTS]


def _get_ping_data(game_details: GameDetails):
    return get_sheet_data(game_details["pingId"], game_details["pingRange"])
