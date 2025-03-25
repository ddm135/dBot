from pathlib import Path
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from app_commands.autocomplete.role import (
    get_role_data,
    role_add_autocomplete,
    role_remove_autocomplete,
    role_set_autocomplete,
    update_role_data,
)
from statics.consts import (
    OWNER_ID,
    ROLE_STORAGE_CHANNEL,
    ROLES,
    SSRG_ROLE_MOD,
    SSRG_ROLE_SS,
    TEST_ROLE_OWNER,
)

if TYPE_CHECKING:
    from dBot import dBot


@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
class Role(commands.GroupCog, name="role", description="Manage Group Roles"):
    LOCKED = Path("data/role/locked")

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    @staticmethod
    def in_channels(itr: discord.Interaction["dBot"]) -> bool:
        return itr.channel_id in ROLE_STORAGE_CHANNEL.values()

    @app_commands.command(name="force_add")
    @app_commands.check(in_channels)
    async def force_add(
        self,
        itr: discord.Interaction["dBot"],
        member: discord.Member,
        role: discord.Role,
    ) -> None:
        await itr.response.defer()
        if not itr.user.id == OWNER_ID or not itr.user.guild_permissions.manage_roles:
            raise app_commands.errors.MissingPermissions(
                missing_permissions=["manage_roles"],
            )

        if not self.bot.info_data_ready:
            return await itr.followup.send(
                "Role data synchronization in progress, feature unavailable.",
            )

        assert itr.guild
        user_id = member.id
        stored_roles = get_role_data(user_id)
        user_roles = member.roles

        if role.id not in ROLES[itr.guild.id]:
            return await itr.response.send_message("This role cannot be added.")
        if role in user_roles:
            return await itr.followup.send("Role is already applied.")
        if role.id in stored_roles:
            return await itr.followup.send("Role is already in inventory.")

        stored_roles.add(role.id)
        update_role_data(user_id, stored_roles)
        self.LOCKED.touch()
        await itr.followup.send(
            f"Added {role.mention} to {member.mention}'s inventory!",
            allowed_mentions=discord.AllowedMentions.none(),
            silent=True,
        )

    @app_commands.command(name="force_remove")
    @app_commands.check(in_channels)
    async def force_remove(
        self,
        itr: discord.Interaction["dBot"],
        member: discord.Member,
        role: discord.Role,
    ) -> None:
        await itr.response.defer()
        if not itr.user.id == OWNER_ID or not itr.user.guild_permissions.manage_roles:
            raise app_commands.errors.MissingPermissions(
                missing_permissions=["manage_roles"],
            )

        if not self.bot.info_data_ready:
            return await itr.followup.send(
                "Role data synchronization in progress, feature unavailable.",
            )

        assert itr.guild
        user_id = member.id
        stored_roles = get_role_data(user_id)
        user_roles = member.roles
        removed = False

        if role.id not in ROLES[itr.guild.id]:
            return await itr.response.send_message("This role cannot be removed.")
        if role in user_roles:
            await member.remove_roles(role)
            removed = True
        if role.id in stored_roles:
            stored_roles.remove(role.id)
            update_role_data(user_id, stored_roles)
            self.LOCKED.touch()
            removed = True
        if not removed:
            return await itr.followup.send("Role is neither applied nor in inventory.")

        await itr.followup.send(
            f"Removed {role.mention} from {member.mention}!",
            allowed_mentions=discord.AllowedMentions.none(),
            silent=True,
        )

    @app_commands.command(name="add")
    @app_commands.autocomplete(role=role_add_autocomplete)
    @app_commands.check(in_channels)
    @app_commands.checks.has_any_role(TEST_ROLE_OWNER, SSRG_ROLE_MOD, SSRG_ROLE_SS)
    async def role_add(self, itr: discord.Interaction["dBot"], role: str) -> None:
        """Apply a Group Role you own in inventory (Requires SUPERSTAR Role)

        Parameters
        -----------
        role: :class:`str`
            Role
        """

        await itr.response.defer()
        if not self.bot.info_data_ready:
            return await itr.followup.send(
                "Role data synchronization in progress, feature unavailable.",
            )

        user_id = itr.user.id
        stored_roles = get_role_data(user_id)
        assert itr.guild
        assert isinstance(itr.user, discord.Member)
        role_name, _, role_id = role.rpartition(" | ")
        user_roles = itr.user.roles
        guild_roles = itr.guild.roles

        try:
            target_role = discord.utils.get(
                guild_roles, name=role_name, id=int(role_id)
            )
            if not target_role:
                return await itr.followup.send("Role not found.")
            if target_role in user_roles:
                return await itr.followup.send("Role is already applied.")
            if target_role.id not in stored_roles:
                return await itr.followup.send("You do not own this role.")
            stored_roles.remove(target_role.id)
            update_role_data(user_id, stored_roles)
            self.LOCKED.touch()
            await itr.user.add_roles(target_role)
            await itr.followup.send(
                f"Added {target_role.mention}!",
                allowed_mentions=discord.AllowedMentions.none(),
                silent=True,
            )
        except ValueError:
            await itr.followup.send("Role not found.")

    @app_commands.command(name="remove")
    @app_commands.autocomplete(role=role_remove_autocomplete)
    @app_commands.check(in_channels)
    @app_commands.checks.has_any_role(TEST_ROLE_OWNER, SSRG_ROLE_MOD, SSRG_ROLE_SS)
    async def role_remove(self, itr: discord.Interaction["dBot"], role: str) -> None:
        """Store a Group Role you own in inventory (Requires SUPERSTAR Role)

        Parameters
        -----------
        role: :class:`str`
            Role
        """

        await itr.response.defer()
        if not self.bot.info_data_ready:
            return await itr.followup.send(
                "Role data synchronization in progress, feature unavailable.",
            )

        user_id = itr.user.id
        stored_roles = get_role_data(user_id)
        assert itr.guild
        assert isinstance(itr.user, discord.Member)
        role_name, _, role_id = role.rpartition(" | ")
        user_roles = itr.user.roles
        group_roles = ROLES[itr.guild.id]
        guild_roles = itr.guild.roles

        try:
            target_role = discord.utils.get(
                guild_roles, name=role_name, id=int(role_id)
            )
            if not target_role:
                return await itr.followup.send("Role not found.")
            if target_role.id not in group_roles:
                return await itr.followup.send("This role cannot be removed.")
            if target_role not in user_roles:
                return await itr.followup.send("You do not own this role.")
            stored_roles.add(target_role.id)
            update_role_data(user_id, stored_roles)
            self.LOCKED.touch()
            await itr.user.remove_roles(target_role)
            await itr.followup.send(
                f"Removed {target_role.mention}!",
                allowed_mentions=discord.AllowedMentions.none(),
                silent=True,
            )
        except ValueError:
            await itr.followup.send("Role not found.")

    @app_commands.command(name="set")
    @app_commands.autocomplete(role=role_set_autocomplete)
    @app_commands.check(in_channels)
    @app_commands.checks.has_any_role(TEST_ROLE_OWNER, SSRG_ROLE_MOD, SSRG_ROLE_SS)
    async def role_set(self, itr: discord.Interaction["dBot"], role: str) -> None:
        """Store higher Group Roles then apply chosen and lower Group Roles
        (Requires SUPERSTAR Role)

        Parameters
        -----------
        role: :class:`str`
            Role
        """

        await itr.response.defer()
        if not self.bot.info_data_ready:
            return await itr.followup.send(
                "Role data synchronization in progress, feature unavailable.",
            )

        user_id = itr.user.id
        stored_roles = get_role_data(user_id)
        assert itr.guild
        assert isinstance(itr.user, discord.Member)
        role_name, _, role_id = role.rpartition(" | ")
        user_roles = itr.user.roles
        group_roles = ROLES[itr.guild.id]
        guild_roles = itr.guild.roles

        try:
            target_role = discord.utils.get(
                guild_roles, name=role_name, id=int(role_id)
            )
            if not target_role:
                return await itr.followup.send("Role not found.")
            if target_role.id not in group_roles:
                return await itr.followup.send("This role is not a Group Role.")
            if target_role.id not in stored_roles and target_role not in user_roles:
                return await itr.followup.send("You do not own this role.")
            target_index = guild_roles.index(target_role)
            remove_roles = tuple(
                r
                for i, r in enumerate(guild_roles)
                if r.id in group_roles and i > target_index and r in user_roles
            )
            add_roles = tuple(
                r
                for i, r in enumerate(guild_roles)
                if r.id in group_roles and i <= target_index and r.id in stored_roles
            )
            stored_roles.difference_update(r.id for r in add_roles)
            stored_roles.update(r.id for r in remove_roles)
            update_role_data(user_id, stored_roles)
            self.LOCKED.touch()
            await itr.user.add_roles(*add_roles)
            await itr.user.remove_roles(*remove_roles)

            embed_description = ""
            if add_roles:
                embed_description += "**Applied**\n"
                embed_description += "\n".join(
                    f"{r.mention}" for r in reversed(add_roles)
                )

                if remove_roles:
                    embed_description += "\n\n"
            if remove_roles:
                embed_description += "**Stored**\n"
                embed_description += "\n".join(
                    f"{r.mention}" for r in reversed(remove_roles)
                )
            embed = discord.Embed(
                title="Changes",
                description=embed_description or "None",
                color=target_role.color,
            )
            await itr.followup.send(
                f"Set to {target_role.mention}!",
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
                silent=True,
            )
        except ValueError:
            await itr.followup.send("Role not found.")

    @app_commands.command(name="inventory")
    @app_commands.check(in_channels)
    async def role_inventory(self, itr: discord.Interaction["dBot"]) -> None:
        """View your Group Role inventory"""

        await itr.response.defer()
        user_id = itr.user.id
        stored_roles = get_role_data(user_id)
        assert itr.guild
        assert isinstance(itr.user, discord.Member)
        group_roles = ROLES[itr.guild.id]
        sorted_stored_roles = sorted(
            (role for role in stored_roles if role in group_roles),
            key=lambda x: group_roles.index(x),
        )
        embed = discord.Embed(
            title="Inventory",
            description=(
                "\n".join(f"<@&{role}>" for role in sorted_stored_roles)
                if sorted_stored_roles
                else "Empty"
            ),
            color=itr.user.color,
        )
        await itr.followup.send(
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
            silent=True,
        )

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, app_commands.errors.MissingAnyRole) or isinstance(
            error, app_commands.errors.MissingPermissions
        ):
            return await interaction.response.send_message(
                "You do not have permission to use this command.",
            )

        if isinstance(error, app_commands.errors.CheckFailure):
            assert (guild_id := interaction.guild_id)
            return await interaction.response.send_message(
                f"wrong channel bruv <#{ROLE_STORAGE_CHANNEL[guild_id]}>",
                ephemeral=True,
            )

        await super().cog_app_command_error(interaction, error)
        raise error


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Role(bot))
