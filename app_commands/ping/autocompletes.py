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
    guild_id = str(itr.guild_id)

    words = (
        app_commands.Choice(name=word, value=word)
        for word in itr.client.word_pings[guild_id]
        if current.lower() in word.lower()
        and itr.client.word_pings[guild_id][word][str(itr.user.id)]
    )

    return list(islice(words, MAX_AUTOCOMPLETE))
