import importlib
import json
import sys
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from statics.consts import ROLE_DATA, ROLES

if (AUTOCOMPLETES := "app_commands.autocompletes.role") in sys.modules:
    importlib.reload(sys.modules[AUTOCOMPLETES])
from app_commands.autocompletes.role import (
    role_add_autocomplete,
    role_remove_autocomplete,
    role_set_autocomplete,
)

if TYPE_CHECKING:
    from dBot import dBot


@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
class Role(commands.GroupCog, name="role", description="Manage SuperStar Roles"):
    NOTICE = (
        "bonusBot and dBot do not share databases and as such, "
        "storing roles on dBot will affect bonusBot's functionalities."
    )

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
        if not self.bot.info_data_ready:
            return await itr.followup.send(
                "Role data synchronization in progress, feature unavailable.",
            )

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
        self.save_role_data()
        await itr.followup.send(
            f"Added {target_role.mention}!\n-# {self.NOTICE}",
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
        if not self.bot.info_data_ready:
            return await itr.followup.send(
                "Role data synchronization in progress, feature unavailable.",
            )

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
        self.save_role_data()
        await itr.followup.send(
            f"Removed {target_role.mention}!\n-# {self.NOTICE}",
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
        if not self.bot.info_data_ready:
            return await itr.followup.send(
                "Role data synchronization in progress, feature unavailable.",
            )

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
        self.save_role_data()

        embed_description = ""
        if add_roles:
            embed_description += "**Applied**\n"
            embed_description += "\n".join(f"{r.mention}" for r in reversed(add_roles))

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
        embed.set_footer(text=self.NOTICE)
        await itr.followup.send(
            f"Set to {target_role.mention}!",
            embed=embed,
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
        embed.set_footer(text=self.NOTICE)
        await itr.followup.send(
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
            silent=True,
        )

    def save_role_data(self) -> None:
        with open(ROLE_DATA, "w") as f:
            json.dump(self.bot.roles, f, indent=4)


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Role(bot))
