from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, tasks

from app_commands.autocomplete.role import (
    _get_role_data,
    _update_role_data,
    role_add_autocomplete,
    role_remove_autocomplete,
)
from static.dConsts import (
    ROLE_STORAGE_CHANNEL,
    SSRG_ROLE_MOD,
    SSRG_ROLE_SS,
    TEST_ROLE_OWNER,
)
from static.dHelpers import get_sheet_data, update_sheet_data


class Role(
    commands.GroupCog, name="role", description="Add/Remove Group Roles you own"
):
    LOCKED = Path("data/role/locked")

    def __init__(self, bot: commands.Bot) -> None:
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
        description="Add a Group Role you own in storage (Requires SUPERSTAR Role)",
    )
    @app_commands.autocomplete(role=role_add_autocomplete)
    @app_commands.checks.has_any_role(TEST_ROLE_OWNER, SSRG_ROLE_MOD, SSRG_ROLE_SS)
    @app_commands.check(in_channels)
    async def role_add(self, itr: discord.Interaction, role: str) -> None:
        await itr.response.defer()
        stored_roles = _get_role_data(itr.user.id)
        assert itr.guild
        assert isinstance(itr.user, discord.Member)
        role_args = role.rsplit(" | ", 1)

        try:
            _role = discord.utils.get(
                itr.guild.roles, name=role_args[0], id=int(role_args[1])
            )
            if not _role:
                await itr.followup.send("Role not found.", silent=True)
                return
            if _role.id not in stored_roles:
                if _role in itr.user.roles:
                    await itr.followup.send("Role is not in storage.", silent=True)
                    return
                await itr.followup.send("You do not own this role.", silent=True)
                return
            stored_roles.remove(_role.id)
            _update_role_data(itr.user.id, stored_roles)
            self.LOCKED.touch()
            await itr.user.add_roles(_role)
            await itr.followup.send(f"Added <@&{_role.id}>!", silent=True)
        except (ValueError, IndexError):
            await itr.followup.send("Role not found.", silent=True)

    @app_commands.command(
        name="remove",
        description="Move a Group Role you own to storage (Requires SUPERSTAR Role)",
    )
    @app_commands.autocomplete(role=role_remove_autocomplete)
    @app_commands.checks.has_any_role(TEST_ROLE_OWNER, SSRG_ROLE_MOD, SSRG_ROLE_SS)
    @app_commands.check(in_channels)
    async def role_remove(self, itr: discord.Interaction, role: str) -> None:
        await itr.response.defer()
        stored_roles = _get_role_data(itr.user.id)
        assert itr.guild
        assert isinstance(itr.user, discord.Member)
        role_args = role.rsplit(" | ", 1)

        try:
            _role = discord.utils.get(
                itr.guild.roles, name=role_args[0], id=int(role_args[1])
            )
            if not _role:
                await itr.followup.send("Role not found.", silent=True)
                return
            if _role not in itr.user.roles:
                await itr.followup.send("You do not own this role.", silent=True)
                return
            stored_roles.append(_role.id)
            _update_role_data(itr.user.id, stored_roles)
            self.LOCKED.touch()
            await itr.user.remove_roles(_role)
            await itr.followup.send(f"Removed <@&{_role.id}>!", silent=True)
        except (ValueError, IndexError):
            await itr.followup.send("Role not found.", silent=True)

    def _download_role_data(self) -> None:
        print("Downloading role data...")
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

        print("Uploading role data...")
        data_path = Path("data/role")
        data_files = data_path.glob("*.txt")
        role_data = []
        for data_file in data_files:
            user_id = data_file.stem
            roles = data_file.read_text()
            role_data.append([user_id, roles])
        update_sheet_data(
            "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s", "Roles!A1", False, role_data
        )
        self.LOCKED.unlink()

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.errors.NoPrivateMessage):
            await interaction.response.send_message(
                "This command cannot be used in direct messages.",
                ephemeral=True,
            )
            return

        if isinstance(error, app_commands.errors.MissingAnyRole):
            await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
            )
            return

        if isinstance(error, app_commands.errors.CheckFailure):
            assert (guild_id := interaction.guild_id)
            await interaction.response.send_message(
                f"wrong channel bruv <#{ROLE_STORAGE_CHANNEL[guild_id]}>",
                ephemeral=True,
            )
            return

        await super().cog_app_command_error(interaction, error)
        raise error

    @tasks.loop(hours=1)
    async def _sync_role_data(self):
        self._upload_role_data()

    @_sync_role_data.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Role(bot))
