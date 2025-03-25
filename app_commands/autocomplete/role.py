from typing import TYPE_CHECKING

import discord
from discord import app_commands

from statics.consts import MAX_AUTOCOMPLETE, ROLES

if TYPE_CHECKING:
    from dBot import dBot


async def role_add_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    if not itr.guild:
        return []
    assert isinstance(itr.user, discord.Member)
    user_roles = itr.user.roles
    group_roles = ROLES[itr.guild.id]
    guild_roles = itr.guild.roles

    roles = [
        app_commands.Choice(
            name=f"{role.name}",
            value=f"{role.name} | {role.id}",
        )
        for role in guild_roles
        if role.id in itr.client.roles[str(itr.user.id)]
        and role not in user_roles
        and current.lower() in role.name.lower()
    ]
    roles.sort(
        key=lambda x: group_roles.index(
            int(x.value.rpartition(" | ")[2]),
        )
    )
    return roles[:MAX_AUTOCOMPLETE]


async def role_remove_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    if not itr.guild:
        return []
    assert isinstance(itr.user, discord.Member)
    user_roles = itr.user.roles
    group_roles = ROLES[itr.guild.id]

    roles = [
        app_commands.Choice(
            name=f"{role.name}",
            value=f"{role.name} | {role.id}",
        )
        for role in user_roles
        if role.id in group_roles and current.lower() in role.name.lower()
    ]
    roles.sort(
        key=lambda x: group_roles.index(
            int(x.value.rpartition(" | ")[2]),
        )
    )
    return roles[:MAX_AUTOCOMPLETE]


async def role_set_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    if not itr.guild:
        return []
    assert isinstance(itr.user, discord.Member)
    user_roles = itr.user.roles
    group_roles = ROLES[itr.guild.id]
    guild_roles = itr.guild.roles

    roles = [
        app_commands.Choice(
            name=f"{role.name}",
            value=f"{role.name} | {role.id}",
        )
        for role in guild_roles
        if role.id in group_roles
        and (role.id in itr.client.roles[str(itr.user.id)] or role in user_roles)
        and current.lower() in role.name.lower()
    ]
    roles.sort(
        key=lambda x: group_roles.index(
            int(x.value.rpartition(" | ")[2]),
        )
    )
    return roles[:MAX_AUTOCOMPLETE]
