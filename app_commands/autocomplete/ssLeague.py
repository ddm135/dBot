from itertools import islice

import discord
from discord import app_commands

from static.dConsts import SSLS, sheetService


async def artist_autocomplete(
    itr: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    game = SSLS[itr.namespace.game]
    result = (
        sheetService.values()
        .get(
            spreadsheetId=game["spreadsheetId"],
            range=game["spreadsheetRange"],
        )
        .execute()
    )
    values = result.get("values", [])
    artists = list(
        dict.fromkeys(
            list(zip(*values))[game["spreadsheetColumns"].index("artist_name")]
        )
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
    game = SSLS[itr.namespace.game]
    artist_name = itr.namespace.artist_name
    result = (
        sheetService.values()
        .get(
            spreadsheetId=game["spreadsheetId"],
            range=game["spreadsheetRange"],
        )
        .execute()
    )
    songs = result.get("values", [])

    return list(
        islice(
            [
                app_commands.Choice(
                    name=song[game["spreadsheetColumns"].index("song_name")],
                    value=song[game["spreadsheetColumns"].index("song_name")],
                )
                for song in songs
                if artist_name == song[game["spreadsheetColumns"].index("artist_name")]
                and current.lower()
                in song[game["spreadsheetColumns"].index("song_name")].lower()
            ],
            25,
        )
    )


async def song_id_autocomplete(
    itr: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    game = SSLS[itr.namespace.game]
    result = (
        sheetService.values()
        .get(
            spreadsheetId=game["spreadsheetId"],
            range=game["spreadsheetRange"],
        )
        .execute()
    )
    songs = result.get("values", [])

    return list(
        islice(
            [
                app_commands.Choice(
                    name=(
                        f"{song[game["spreadsheetColumns"].index("artist_name")]} - "
                        f"{song[game["spreadsheetColumns"].index("song_name")]}"
                    ),
                    value=song[game["spreadsheetColumns"].index("song_id")],
                )
                for song in songs
                if current == song[game["spreadsheetColumns"].index("song_id")]
            ],
            25,
        )
    )
