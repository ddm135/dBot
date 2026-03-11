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

    artists = itr.client.artist[game]
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

    info_columns = GAMES[game]["spreadsheet"]["columns"][0]
    if "search_term" in info_columns:
        search_term_index = info_columns.index("search_term")
    else:
        search_term_index = None
    if not (songs := itr.client.info_by_name[game].get(itr.namespace.artist, {})):
        return []

    song_choices = (
        app_commands.Choice(name=song_name, value=song_name)
        for song_name, song_details in songs.items()
        if current.lower() in song_name.lower()
        or (
            search_term_index is not None
            and current.lower() in song_details[search_term_index].lower()
        )
    )

    return list(islice(song_choices, MAX_AUTOCOMPLETE))


async def season_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[int]]:
    if not (game := itr.namespace.game):
        return []

    seasons = itr.client.world_record[game]
    date_format = GAMES[game]["dateFormat"]
    season_choices = (
        app_commands.Choice(
            name=(
                f"Season {code} ({season["start"].strftime(date_format)} - "
                f"{season["end"].strftime(date_format)})"
            ),
            value=code,
        )
        for code, season in seasons.items()
        if current in str(code)
    )

    return list(islice(season_choices, MAX_AUTOCOMPLETE))
