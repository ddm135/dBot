from pathlib import Path
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from static.dConsts import MAX_AUTOCOMPLETE_RESULTS, ROLES

if TYPE_CHECKING:
    from dBot import dBot


async def role_add_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    if not itr.guild or not itr.client.role_data_ready:
        return []
    assert isinstance(itr.user, discord.Member)
    stored_roles = get_role_data(itr.user.id)
    user_roles = itr.user.roles
    group_roles = ROLES[itr.guild.id]
    guild_roles = itr.guild.roles

    roles = [
        app_commands.Choice(
            name=f"{role.name}",
            value=f"{role.name} | {role.id}",
        )
        for role in guild_roles
        if role.id in stored_roles
        and role not in user_roles
        and current.lower() in role.name.lower()
    ]
    roles.sort(
        key=lambda x: group_roles.index(
            int(x.value.rsplit(" | ", 1)[1]),
        )
    )
    return roles[:MAX_AUTOCOMPLETE_RESULTS]


async def role_remove_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    if not itr.guild or not itr.client.role_data_ready:
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
            int(x.value.rsplit(" | ", 1)[1]),
        )
    )
    return roles[:MAX_AUTOCOMPLETE_RESULTS]


async def role_set_autocomplete(
    itr: discord.Interaction["dBot"], current: str
) -> list[app_commands.Choice[str]]:
    if not itr.guild or not itr.client.role_data_ready:
        return []
    assert isinstance(itr.user, discord.Member)
    stored_roles = get_role_data(itr.user.id)
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
        and (role.id in stored_roles or role in user_roles)
        and current.lower() in role.name.lower()
    ]
    roles.sort(
        key=lambda x: group_roles.index(
            int(x.value.rsplit(" | ", 1)[1]),
        )
    )
    return roles[:MAX_AUTOCOMPLETE_RESULTS]


def get_role_data(user_id: int) -> set[int]:
    role_file = Path(f"data/role/{user_id}.txt")
    if not role_file.exists():
        return set()
    role_str = role_file.read_text()
    return {int(role) for role in role_str.split(",") if role_str}


def update_role_data(user_id: int, roles: set[int]) -> None:
    role_file = Path(f"data/role/{user_id}.txt")
    role_str = ",".join(str(role) for role in roles)
    role_file.write_text(role_str)
