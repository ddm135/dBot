from itertools import islice

import discord
from discord import app_commands

from static.dConsts import GAMES
from static.dServices import sheetService


async def artist_autocomplete(
    itr: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    gameD = GAMES[itr.namespace.game]
    result = (
        sheetService.values()
        .get(
            spreadsheetId=gameD["sslId"],
            range=gameD["sslRange"],
        )
        .execute()
    )
    values = result.get("values", [])
    artists = list(
        dict.fromkeys(list(zip(*values))[gameD["sslColumns"].index("artist_name")])
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


async def song_autocomplete(
    itr: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    gameD = GAMES[itr.namespace.game]
    artist_name = itr.namespace.artist_name
    result = (
        sheetService.values()
        .get(
            spreadsheetId=gameD["sslId"],
            range=gameD["sslRange"],
        )
        .execute()
    )
    songs = result.get("values", [])

    return list(
        islice(
            [
                app_commands.Choice(
                    name=song[gameD["sslColumns"].index("song_name")],
                    value=song[gameD["sslColumns"].index("song_name")],
                )
                for song in songs
                if artist_name == song[gameD["sslColumns"].index("artist_name")]
                and current.lower()
                in song[gameD["sslColumns"].index("song_name")].lower()
            ],
            25,
        )
    )


async def song_id_autocomplete(
    itr: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    gameD = GAMES[itr.namespace.game]
    result = (
        sheetService.values()
        .get(
            spreadsheetId=gameD["sslId"],
            range=gameD["sslRange"],
        )
        .execute()
    )
    songs = result.get("values", [])

    return list(
        islice(
            [
                app_commands.Choice(
                    name=(
                        f"{song[gameD["sslColumns"].index("artist_name")]} - "
                        f"{song[gameD["sslColumns"].index("song_name")]}"
                    ),
                    value=song[gameD["sslColumns"].index("song_id")],
                )
                for song in songs
                if current == song[gameD["sslColumns"].index("song_id")]
            ],
            25,
        )
    )
