import logging
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands, tasks

from app_commands.autocomplete.role import (
    _get_role_data,
    _update_role_data,
    role_add_autocomplete,
    role_remove_autocomplete,
    role_set_autocomplete,
)
from static.dConsts import (
    ROLE_STORAGE_CHANNEL,
    ROLES,
    SSRG_ROLE_MOD,
    SSRG_ROLE_SS,
    TEST_ROLE_OWNER,
)
from static.dHelpers import clear_sheet_data, get_sheet_data, update_sheet_data

if TYPE_CHECKING:
    from dBot import dBot


@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
class Role(commands.GroupCog, name="role", description="Manage Group Roles"):
    LOCKED = Path("data/role/locked")
    ROLE_LOGGER = logging.getLogger(__name__)
    NOTICE = (
        "-# bonusBot and dBot does not share databases and as such, storing "
        "roles on dBot will affect bonusBot role storage and shop functionality."
    )

    def __init__(self, bot: dBot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        if self.LOCKED.exists():
            self._upload_role_data()
        else:
            self._download_role_data()
        self._sync_role_data.start()
        await super().cog_load()

    async def cog_unload(self) -> None:
        self._sync_role_data.cancel()
        self._upload_role_data()
        await super().cog_unload()

    @staticmethod
    def in_channels(itr: discord.Interaction) -> bool:
        return itr.channel_id in ROLE_STORAGE_CHANNEL.values()

    @app_commands.command(
        name="add",
        description="Apply a Group Role you own in inventory (Requires SUPERSTAR Role)",
    )
    @app_commands.autocomplete(role=role_add_autocomplete)
    @app_commands.checks.has_any_role(TEST_ROLE_OWNER, SSRG_ROLE_MOD, SSRG_ROLE_SS)
    @app_commands.check(in_channels)
    async def role_add(self, itr: discord.Interaction, role: str) -> None:
        await itr.response.defer()
        user_id = itr.user.id
        stored_roles = _get_role_data(user_id)
        assert itr.guild
        assert isinstance(itr.user, discord.Member)
        role_args = role.rsplit(" | ", 1)
        user_roles = itr.user.roles
        guild_roles = itr.guild.roles

        try:
            target_role = discord.utils.get(
                guild_roles, name=role_args[0], id=int(role_args[1])
            )
            if not target_role:
                return await itr.followup.send(f"Role not found.\n{self.NOTICE}")
            if target_role in user_roles:
                return await itr.followup.send(
                    f"Role is already applied.\n{self.NOTICE}"
                )
            if target_role.id not in stored_roles:
                return await itr.followup.send(
                    f"You do not own this role.\n{self.NOTICE}"
                )
            stored_roles.remove(target_role.id)
            _update_role_data(itr.user.id, stored_roles)
            self.LOCKED.touch()
            await itr.user.add_roles(target_role)
            await itr.followup.send(
                f"Added <@&{target_role.id}>!\n{self.NOTICE}",
                allowed_mentions=discord.AllowedMentions.none(),
                silent=True,
            )
        except (ValueError, IndexError):
            await itr.followup.send(f"Role not found.\n{self.NOTICE}")

    @app_commands.command(
        name="remove",
        description="Store a Group Role you own in inventory (Requires SUPERSTAR Role)",
    )
    @app_commands.autocomplete(role=role_remove_autocomplete)
    @app_commands.checks.has_any_role(TEST_ROLE_OWNER, SSRG_ROLE_MOD, SSRG_ROLE_SS)
    @app_commands.check(in_channels)
    async def role_remove(self, itr: discord.Interaction, role: str) -> None:
        await itr.response.defer()
        user_id = itr.user.id
        stored_roles = _get_role_data(user_id)
        assert itr.guild
        assert isinstance(itr.user, discord.Member)
        role_args = role.rsplit(" | ", 1)
        user_roles = itr.user.roles
        group_roles = ROLES[itr.guild.id]
        guild_roles = itr.guild.roles

        try:
            target_role = discord.utils.get(
                guild_roles, name=role_args[0], id=int(role_args[1])
            )
            if not target_role:
                return await itr.followup.send(f"Role not found.\n{self.NOTICE}")
            if target_role.id not in group_roles:
                return await itr.followup.send(
                    f"This role cannot be removed.\n{self.NOTICE}"
                )
            if target_role not in user_roles:
                return await itr.followup.send(
                    f"You do not own this role.\n{self.NOTICE}"
                )
            stored_roles.add(target_role.id)
            _update_role_data(user_id, stored_roles)
            self.LOCKED.touch()
            await itr.user.remove_roles(target_role)
            await itr.followup.send(
                f"Removed <@&{target_role.id}>!\n{self.NOTICE}",
                allowed_mentions=discord.AllowedMentions.none(),
                silent=True,
            )
        except (ValueError, IndexError):
            await itr.followup.send(f"Role not found.\n{self.NOTICE}")

    @app_commands.command(
        name="set",
        description=(
            "Store higher Group Roles then apply chosen and lower Group Roles "
            "(Requires SUPERSTAR Role)"
        ),
    )
    @app_commands.autocomplete(role=role_set_autocomplete)
    @app_commands.checks.has_any_role(TEST_ROLE_OWNER, SSRG_ROLE_MOD, SSRG_ROLE_SS)
    @app_commands.check(in_channels)
    async def role_set(self, itr: discord.Interaction, role: str) -> None:
        await itr.response.defer()
        user_id = itr.user.id
        stored_roles = _get_role_data(user_id)
        assert itr.guild
        assert isinstance(itr.user, discord.Member)
        role_args = role.rsplit(" | ", 1)
        user_roles = itr.user.roles
        group_roles = ROLES[itr.guild.id]
        guild_roles = itr.guild.roles

        try:
            target_role = discord.utils.get(
                guild_roles, name=role_args[0], id=int(role_args[1])
            )
            if not target_role:
                return await itr.followup.send(f"Role not found.\n{self.NOTICE}")
            if target_role.id not in group_roles:
                return await itr.followup.send(
                    f"This role is not a Group Role.\n{self.NOTICE}"
                )
            if target_role.id not in stored_roles and target_role not in user_roles:
                return await itr.followup.send(
                    f"You do not own this role.\n{self.NOTICE}"
                )
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
            _update_role_data(user_id, stored_roles)
            self.LOCKED.touch()
            await itr.user.add_roles(*add_roles)
            await itr.user.remove_roles(*remove_roles)

            embed_description = ""
            if add_roles:
                embed_description += "**Applied**\n"
                embed_description += "\n".join(
                    f"<@&{r.id}>" for r in reversed(add_roles)
                )

                if remove_roles:
                    embed_description += "\n\n"
            if remove_roles:
                embed_description += "**Stored**\n"
                embed_description += "\n".join(
                    f"<@&{r.id}>" for r in reversed(remove_roles)
                )
            embed = discord.Embed(
                title="Changes",
                description=embed_description or "None",
                color=target_role.color,
            )
            embed.set_footer(text=self.NOTICE)
            await itr.followup.send(
                f"Set to <@&{target_role.id}>!",
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
                silent=True,
            )
        except (ValueError, IndexError):
            await itr.followup.send(f"Role not found.\n{self.NOTICE}")

    @app_commands.command(
        name="inventory",
        description=("View your Group Role inventory"),
    )
    @app_commands.check(in_channels)
    async def role_inventory(self, itr: discord.Interaction) -> None:
        await itr.response.defer()
        user_id = itr.user.id
        stored_roles = _get_role_data(user_id)
        assert itr.guild
        assert isinstance(itr.user, discord.Member)
        group_roles = ROLES[itr.guild.id]
        sorted_stored_roles = sorted(
            tuple(role for role in stored_roles if role in group_roles),
            key=lambda x: group_roles.index(x),
        )
        embed = discord.Embed(
            title=f"{itr.user.name}'s Inventory",
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

    def _download_role_data(self) -> None:
        if self.LOCKED.exists():
            return

        self.ROLE_LOGGER.info("Downloading role data...")
        data_path = Path("data/role")
        data_files = data_path.glob("*.txt")
        for data_file in data_files:
            data_file.unlink()
        role_data = get_sheet_data(
            "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s", "Roles!A:C"
        )
        for row in role_data:
            file_path = Path(f"data/role/{row[0]}.txt")
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(row[1])

    def _upload_role_data(self) -> None:
        if not self.LOCKED.exists():
            return

        self.ROLE_LOGGER.info("Uploading role data...")
        data_path = Path("data/role")
        data_files = data_path.glob("*.txt")
        role_data = []
        for data_file in data_files:
            user_id = data_file.stem
            roles = data_file.read_text()
            role_data.append([user_id, roles, "."])
        clear_sheet_data("1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s", "Roles")
        update_sheet_data(
            "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s", "Roles!A1", False, role_data
        )
        self.LOCKED.unlink()

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.errors.MissingAnyRole):
            return await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
            )

        if isinstance(error, app_commands.errors.CheckFailure):
            assert (guild_id := interaction.guild_id)
            return await interaction.response.send_message(
                f"wrong channel bruv <#{ROLE_STORAGE_CHANNEL[guild_id]}>",
                ephemeral=True,
            )

        await super().cog_app_command_error(interaction, error)
        raise error

    @tasks.loop(hours=1)
    async def _sync_role_data(self):
        self._upload_role_data()

    @_sync_role_data.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot: dBot) -> None:
    await bot.add_cog(Role(bot))
