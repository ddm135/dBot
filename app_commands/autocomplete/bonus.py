from itertools import islice

import discord
from discord import app_commands

from static.dConsts import BONUSES, sheetService


async def artist_autocomplete(
    itr: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    game = BONUSES[itr.namespace.game]
    result = (
        sheetService.values()
        .get(
            spreadsheetId=game["pingId"],
            range=game["pingRange"],
        )
        .execute()
    )
    values = result.get("values", [])
    artists = list(
        dict.fromkeys(list(zip(*values))[game["pingColumns"].index("artist_name")])
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
