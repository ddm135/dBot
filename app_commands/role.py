import discord
from discord import app_commands
from discord.ext import commands

from app_commands.autocomplete.role import (
    _get_role_data,
    _update_role_data,
    role_add_autocomplete,
    role_remove_autocomplete,
)
from static.dConsts import OK_ROLE_OWNER, SSRG_ROLE_MOD, SSRG_ROLE_SS


class Role(commands.GroupCog, name="role"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="add")
    @app_commands.autocomplete(role=role_add_autocomplete)
    @app_commands.checks.has_any_role(OK_ROLE_OWNER, SSRG_ROLE_MOD, SSRG_ROLE_SS)
    async def role_add(self, itr: discord.Interaction, role: str) -> None:
        await itr.response.defer(ephemeral=True)
        user_index, stored_roles = _get_role_data(itr.user.id)
        assert itr.guild
        _role = discord.utils.get(itr.guild.roles, id=int(role))
        if not _role:
            await itr.followup.send("Role not found.", ephemeral=True)
            return
        stored_roles.remove(_role.id)
        _update_role_data(user_index, itr.user.id, stored_roles)
        assert isinstance(itr.user, discord.Member)
        await itr.user.add_roles(_role)
        await itr.followup.send(f"Added <@&{_role.id}>!", ephemeral=True)

    @app_commands.command(name="remove")
    @app_commands.autocomplete(role=role_remove_autocomplete)
    @app_commands.checks.has_any_role(OK_ROLE_OWNER, SSRG_ROLE_MOD, SSRG_ROLE_SS)
    async def role_remove(self, itr: discord.Interaction, role: str) -> None:
        await itr.response.defer(ephemeral=True)
        user_index, stored_roles = _get_role_data(itr.user.id)
        assert itr.guild
        _role = discord.utils.get(itr.guild.roles, id=int(role))
        if not _role:
            await itr.followup.send("Role not found.", ephemeral=True)
            return
        stored_roles.append(_role.id)
        _update_role_data(user_index, itr.user.id, stored_roles)
        assert isinstance(itr.user, discord.Member)
        await itr.user.remove_roles(_role)
        await itr.followup.send(f"Removed <@&{_role.id}>!", ephemeral=True)

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.errors.NoPrivateMessage):
            await interaction.response.send_message(
                "This command cannot be used in direct messages.",
                ephemeral=True,
                silent=True,
            )
            return

        if isinstance(error, app_commands.errors.MissingAnyRole):
            await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
                silent=True,
            )
            return

        raise error


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Role(bot))
