from pathlib import Path

import discord
from discord import app_commands

from static.dConsts import MAX_AUTOCOMPLETE_RESULTS, ROLES


async def role_add_autocomplete(
    itr: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    if not itr.guild:
        return []
    assert isinstance(itr.user, discord.Member)
    assert (guild_id := itr.guild_id)
    stored_roles = _get_role_data(itr.user.id)

    roles = [
        app_commands.Choice(
            name=f"{role.name}",
            value=f"{role.name} | {role.id}",
        )
        for role in itr.guild.roles
        if current.lower() in role.name.lower()
        and role.id in stored_roles
        and role.id not in [r.id for r in itr.user.roles]
    ]
    roles.sort(key=lambda x: ROLES[guild_id].index(int(x.value.rsplit(" | ", 1)[1])))
    return roles[:MAX_AUTOCOMPLETE_RESULTS]


async def role_remove_autocomplete(
    itr: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    if not itr.guild:
        return []
    assert isinstance(itr.user, discord.Member)
    assert (guild_id := itr.guild_id)

    roles = [
        app_commands.Choice(
            name=f"{role.name}",
            value=f"{role.name} | {role.id}",
        )
        for role in itr.user.roles
        if current.lower() in role.name.lower() and role.id in ROLES[itr.guild_id]
    ]
    roles.sort(key=lambda x: ROLES[guild_id].index(int(x.value.rsplit(" | ", 1)[1])))
    return roles[:MAX_AUTOCOMPLETE_RESULTS]


def _get_role_data(user_id: int) -> list[int]:
    role_file = Path(f"data/role/{user_id}.txt")
    role_str = role_file.read_text()
    return [int(role) for role in role_str.split(",") if role_str]


def _update_role_data(user_id: int, roles: list[int]) -> None:
    role_file = Path(f"data/role/{user_id}.txt")
    role_str = ",".join(str(role) for role in roles)
    role_file.write_text(role_str)
