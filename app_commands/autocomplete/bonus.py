from itertools import islice

import discord
from discord import app_commands

from static.dConsts import GAMES, sheetService


async def artist_autocomplete(
    itr: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    gameD = GAMES[itr.namespace.game]
    result = (
        sheetService.values()
        .get(
            spreadsheetId=gameD["pingId"],
            range=gameD["pingRange"],
        )
        .execute()
    )
    values = result.get("values", [])
    artists = list(
        dict.fromkeys(list(zip(*values))[gameD["pingColumns"].index("artist_name")])
    )

    return list(
        islice(
            [
                app_commands.Choice(
                    name=artist,
                    value=artist,
                )
                for artist in artists
                if current.lower() in artist.lower()
            ],
            25,
        )
    )
