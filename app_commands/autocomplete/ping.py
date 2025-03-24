from itertools import islice
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from statics.consts import MAX_AUTOCOMPLETE

if TYPE_CHECKING:
    from dBot import dBot


async def word_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    if not itr.guild:
        return []

    words = (
        app_commands.Choice(name=word, value=word)
        for word in itr.client.pings[str(itr.guild.id)]
        if current.lower() in word.lower()
        and str(itr.user.id) in itr.client.pings[word]
    )

    return list(islice(words, MAX_AUTOCOMPLETE))
