import discord
from discord import app_commands

from static.dConsts import MAX_AUTOCOMPLETE_RESULTS, ROLES
from static.dHelpers import get_sheet_data, update_sheet_data


async def role_add_autocomplete(
    itr: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    if not itr.guild:
        return []
    assert isinstance(itr.user, discord.Member)
    assert (guild_id := itr.guild_id)
    _, stored_roles = _get_role_data(itr.user.id)

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


def _get_role_data(user_id: int) -> tuple[int, list[int]]:
    role_data = get_sheet_data(
        "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s", "Roles!A:C"
    )
    user_index = 1
    for index, user in enumerate(role_data, start=1):
        if user[0] == str(user_id):
            return index, [int(role) for role in user[1].split(",") if role]
    return user_index + 1, []


def _update_role_data(user_index: int, user_id: int, roles: list[int]) -> None:
    role_str = ",".join(str(role) for role in roles)
    update_sheet_data(
        "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        f"Roles!A{user_index}",
        False,
        [[str(user_id), role_str, "."]],
    )
