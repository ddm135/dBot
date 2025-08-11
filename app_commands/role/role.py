from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from statics.consts import ROLES, Data

from .autocompletes import (
    role_add_autocomplete,
    role_remove_autocomplete,
    role_set_autocomplete,
)
from .commons import NOTICE
from .embeds import RoleInventoryEmbed, RoleSetEmbed

if TYPE_CHECKING:
    from dBot import dBot


@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
class Role(commands.GroupCog, name="role", description="Manage SuperStar Roles"):
    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    @app_commands.command(name="add")
    @app_commands.autocomplete(role=role_add_autocomplete)
    async def role_add(self, itr: discord.Interaction["dBot"], role: str) -> None:
        """Apply a SuperStar Role you own in inventory

        Parameters
        -----------
        role: :class:`str`
            Role
        """

        await itr.response.defer()
        user_id = str(itr.user.id)
        assert itr.guild
        assert isinstance(itr.user, discord.Member)
        user_roles = itr.user.roles
        group_roles = ROLES[itr.guild.id]
        guild_roles = itr.guild.roles

        target_role = discord.utils.find(
            lambda r: role.lower() == r.name.lower() and r.id in group_roles,
            guild_roles,
        )
        if not target_role:
            return await itr.followup.send("Role not found.")
        if target_role in user_roles:
            return await itr.followup.send("Role is already applied.")
        if target_role.id not in self.bot.roles[user_id]:
            return await itr.followup.send("You do not own this role.")

        self.bot.roles[user_id].remove(target_role.id)
        await itr.user.add_roles(target_role)

        cog = self.bot.get_cog("DataSync")
        cog.save_data(Data.ROLES)  # type: ignore[union-attr]
        await itr.followup.send(
            f"Added {target_role.mention}!\n-# {NOTICE}",
            allowed_mentions=discord.AllowedMentions.none(),
            silent=True,
        )

    @app_commands.command(name="remove")
    @app_commands.autocomplete(role=role_remove_autocomplete)
    async def role_remove(self, itr: discord.Interaction["dBot"], role: str) -> None:
        """Store a SuperStar Role you own in inventory

        Parameters
        -----------
        role: :class:`str`
            Role
        """

        await itr.response.defer()
        user_id = str(itr.user.id)
        assert itr.guild
        assert isinstance(itr.user, discord.Member)
        user_roles = itr.user.roles
        group_roles = ROLES[itr.guild.id]
        guild_roles = itr.guild.roles

        target_role = discord.utils.find(
            lambda r: role.lower() == r.name.lower() and r.id in group_roles,
            guild_roles,
        )
        if not target_role:
            return await itr.followup.send("Role not found.")
        if target_role.id not in group_roles:
            return await itr.followup.send("This role cannot be removed.")
        if target_role not in user_roles:
            return await itr.followup.send("You do not own this role.")

        self.bot.roles[user_id].append(target_role.id)
        await itr.user.remove_roles(target_role)

        cog = self.bot.get_cog("DataSync")
        cog.save_data(Data.ROLES)  # type: ignore[union-attr]
        await itr.followup.send(
            f"Removed {target_role.mention}!\n-# {NOTICE}",
            allowed_mentions=discord.AllowedMentions.none(),
            silent=True,
        )

    @app_commands.command(name="set")
    @app_commands.autocomplete(role=role_set_autocomplete)
    async def role_set(self, itr: discord.Interaction["dBot"], role: str) -> None:
        """Store higher SuperStar Roles then apply chosen and lower SuperStar Roles

        Parameters
        -----------
        role: :class:`str`
            Role
        """

        await itr.response.defer()
        user_id = str(itr.user.id)
        assert itr.guild
        assert isinstance(itr.user, discord.Member)
        user_roles = itr.user.roles
        group_roles = ROLES[itr.guild.id]
        guild_roles = itr.guild.roles

        target_role = discord.utils.find(
            lambda r: role.lower() == r.name.lower() and r.id in group_roles,
            guild_roles,
        )
        if not target_role:
            return await itr.followup.send("Role not found.")
        if target_role.id not in group_roles:
            return await itr.followup.send("This role is not a SuperStar Role.")
        if (
            target_role.id not in self.bot.roles[user_id]
            and target_role not in user_roles
        ):
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
            if r.id in group_roles
            and i <= target_index
            and r.id in self.bot.roles[user_id]
        )

        for r in add_roles:
            if r.id in self.bot.roles[user_id]:
                self.bot.roles[user_id].remove(r.id)
        for r in remove_roles:
            if r.id not in self.bot.roles[user_id]:
                self.bot.roles[user_id].append(r.id)
        await itr.user.add_roles(*add_roles)
        await itr.user.remove_roles(*remove_roles)

        cog = self.bot.get_cog("DataSync")
        cog.save_data(Data.ROLES)  # type: ignore[union-attr]
        await itr.followup.send(
            f"Set to {target_role.mention}!",
            embed=RoleSetEmbed(target_role, add_roles, remove_roles),
            allowed_mentions=discord.AllowedMentions.none(),
            silent=True,
        )

    @app_commands.command(name="inventory")
    async def role_inventory(self, itr: discord.Interaction["dBot"]) -> None:
        """View your SuperStar Role inventory"""

        await itr.response.defer()
        user_id = str(itr.user.id)
        assert itr.guild
        assert isinstance(itr.user, discord.Member)
        group_roles = ROLES[itr.guild.id]
        sorted_stored_roles = sorted(
            (role for role in self.bot.roles[user_id] if role in group_roles),
            key=group_roles.index,
        )

        await itr.followup.send(
            embed=RoleInventoryEmbed(itr.user, sorted_stored_roles),
            allowed_mentions=discord.AllowedMentions.none(),
            silent=True,
        )


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Role(bot))
