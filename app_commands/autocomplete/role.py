import discord
from discord import app_commands

from static.dConsts import MAX_AUTOCOMPLETE_RESULTS, ROLES


async def role_add_autocomplete(
    itr: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    roles = [
        app_commands.Choice(name=role.name, value=str(role.id))
        for role in itr.guild.roles
        if current.lower() in role.name.lower()
        and role.id in ROLES[itr.guild_id]
        and role.id not in [r.id for r in itr.user.roles]
    ]
    return roles[:MAX_AUTOCOMPLETE_RESULTS]


async def role_remove_autocomplete(
    itr: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    roles = [
        app_commands.Choice(name=role.name, value=str(role.id))
        for role in itr.user.roles
        if current.lower() in role.name.lower() and role.id in ROLES[itr.guild_id]
    ]
    return roles[:MAX_AUTOCOMPLETE_RESULTS]
