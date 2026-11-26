"""``/role``: keep SuperStar roles in an inventory and apply the one you want."""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from cogs.common import Itr
from discord_ids import SUPERSTAR_ROLES

if TYPE_CHECKING:
    from bot import dBot

MAX_CHOICES = 25
NOTICE = (
    "bonusBot and dBot do not share databases and as such, "
    "storing roles on dBot will affect bonusBot's functionalities."
)
NO_MENTIONS = discord.AllowedMentions.none()


@dataclass(frozen=True, slots=True)
class RoleChange:
    """What setting a role changes: roles to give from the inventory, and roles to take off
    into it.
    """

    apply: tuple[int, ...]  # role ids to give the member (from their inventory)
    store: tuple[int, ...]  # role ids to take off the member into the inventory


def plan_set(
    guild_order: Sequence[int],
    group_roles: Collection[int],
    target: int,
    worn: Collection[int],
    stored: Collection[int],
) -> RoleChange:
    """Wear ``target`` and the group roles below it; store the ones above.

    ``guild_order`` is the guild's role ids from lowest to highest position.
    """
    position = guild_order.index(target)
    apply = tuple(
        r
        for i, r in enumerate(guild_order)
        if r in group_roles and i <= position and r in stored
    )
    store = tuple(
        r
        for i, r in enumerate(guild_order)
        if r in group_roles and i > position and r in worn
    )
    return RoleChange(apply, store)


def group_roles_of(guild_id: int) -> tuple[int, ...]:
    """The group roles of a guild (none if the guild has none)."""
    return SUPERSTAR_ROLES.get(guild_id, ())


@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.allowed_installs(guilds=True, users=False)
class Role(
    commands.GroupCog,
    name="role",
    description="Manage SuperStar Roles",
):
    """``/role``: SuperStar roles kept in an inventory. A user can store the roles
    they hold, take them back, and wear one: the roles above it are stored.
    """

    def __init__(self, bot: dBot) -> None:
        self.bot = bot

    # -- lookups -------------------------------------------------------------

    @staticmethod
    def _find(guild: discord.Guild, name: str) -> discord.Role | None:
        group = group_roles_of(guild.id)
        wanted = name.casefold()
        return discord.utils.find(
            lambda r: r.name.casefold() == wanted and r.id in group, guild.roles
        )

    @staticmethod
    def _sorted(
        roles: Sequence[discord.Role], group: Sequence[int]
    ) -> list[discord.Role]:
        return sorted(roles, key=lambda r: group.index(r.id))

    async def _choices(
        self, itr: Itr, current: str, *, stored: bool, worn: bool
    ) -> list[app_commands.Choice[str]]:
        if not itr.guild or not isinstance(itr.user, discord.Member):
            return []
        group = group_roles_of(itr.guild.id)
        inventory = await self.bot.db.roles.get(itr.user.id) if stored else set()
        wearing = {r.id for r in itr.user.roles}
        wanted = current.casefold()
        roles = [
            r
            for r in itr.guild.roles
            if r.id in group
            and wanted in r.name.casefold()
            and (
                (stored and r.id in inventory and r.id not in wearing and not worn)
                or (worn and not stored and r.id in wearing)
                or (stored and worn and (r.id in inventory or r.id in wearing))
            )
        ]
        return [
            app_commands.Choice(name=r.name, value=r.name)
            for r in self._sorted(roles, group)[:MAX_CHOICES]
        ]

    async def add_autocomplete(
        self, itr: Itr, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._choices(itr, current, stored=True, worn=False)

    async def remove_autocomplete(
        self, itr: Itr, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._choices(itr, current, stored=False, worn=True)

    async def set_autocomplete(
        self, itr: Itr, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._choices(itr, current, stored=True, worn=True)

    # -- commands ------------------------------------------------------------

    @app_commands.command(name="add")
    @app_commands.autocomplete(role=add_autocomplete)
    async def role_add(self, itr: Itr, role: str) -> None:
        """Apply a SuperStar Role you own in inventory

        Parameters
        ----------
        role: Role
        """
        await itr.response.defer()
        assert itr.guild and isinstance(itr.user, discord.Member)
        target = self._find(itr.guild, role)
        if not target:
            await itr.followup.send("Role not found.")
            return
        if target in itr.user.roles:
            await itr.followup.send("Role is already applied.")
            return
        if target.id not in await self.bot.db.roles.get(itr.user.id):
            await itr.followup.send("You do not own this role.")
            return
        await itr.user.add_roles(target)
        await self.bot.db.roles.remove(itr.user.id, [target.id])
        await itr.followup.send(
            f"Added {target.mention}!\n-# {NOTICE}",
            allowed_mentions=NO_MENTIONS,
            silent=True,
        )

    @app_commands.command(name="remove")
    @app_commands.autocomplete(role=remove_autocomplete)
    async def role_remove(self, itr: Itr, role: str) -> None:
        """Store a SuperStar Role you own in inventory

        Parameters
        ----------
        role: Role
        """
        await itr.response.defer()
        assert itr.guild and isinstance(itr.user, discord.Member)
        target = self._find(itr.guild, role)
        if not target:
            await itr.followup.send("Role not found.")
            return
        if target not in itr.user.roles:
            await itr.followup.send("You do not own this role.")
            return
        await itr.user.remove_roles(target)
        await self.bot.db.roles.add(itr.user.id, [target.id])
        await itr.followup.send(
            f"Removed {target.mention}!\n-# {NOTICE}",
            allowed_mentions=NO_MENTIONS,
            silent=True,
        )

    @app_commands.command(name="set")
    @app_commands.autocomplete(role=set_autocomplete)
    async def role_set(self, itr: Itr, role: str) -> None:
        """Store higher SuperStar Roles then apply chosen and lower SuperStar Roles

        Parameters
        ----------
        role: Role
        """
        # Roles are ranked by position, and a member wears one rank per group: the
        # chosen role plus every lower one are applied, and the higher ones are stored
        # (removed from the member but remembered) so they can be restored later.
        # `plan_set` decides which; this method only validates, applies and reports.
        await itr.response.defer()
        assert itr.guild and isinstance(itr.user, discord.Member)
        target = self._find(itr.guild, role)
        if not target:
            await itr.followup.send("Role not found.")
            return
        stored = await self.bot.db.roles.get(itr.user.id)
        worn = {r.id for r in itr.user.roles}
        # Owned means stored or currently worn; anything else cannot be claimed.
        if target.id not in stored and target.id not in worn:
            await itr.followup.send("You do not own this role.")
            return

        guild_order = [r.id for r in itr.guild.roles]
        change = plan_set(
            guild_order, group_roles_of(itr.guild.id), target.id, worn, stored
        )
        by_id = {r.id: r for r in itr.guild.roles}
        # `apply` and `store` are ids from the guild's own role list, so they resolve.
        add = [by_id[i] for i in change.apply]
        remove = [by_id[i] for i in change.store]
        if add:
            await itr.user.add_roles(*add)
        if remove:
            await itr.user.remove_roles(*remove)
        # Discord first, then the database: if a Discord call fails the stored set
        # still matches what the member wears. Stored roles are the ones taken off.
        await self.bot.db.roles.change(
            itr.user.id, add=change.store, remove=change.apply
        )

        lines = []
        if add:
            lines.append("**Applied**\n" + "\n".join(r.mention for r in reversed(add)))
        if remove:
            lines.append(
                "**Stored**\n" + "\n".join(r.mention for r in reversed(remove))
            )
        embed = discord.Embed(
            title="Changes",
            description="\n\n".join(lines) or "None",
            color=target.color,
        )
        embed.set_footer(text=NOTICE)
        await itr.followup.send(
            f"Set to {target.mention}!",
            embed=embed,
            allowed_mentions=NO_MENTIONS,
            silent=True,
        )

    @app_commands.command(name="inventory")
    async def role_inventory(self, itr: Itr) -> None:
        """View your SuperStar Role inventory"""
        await itr.response.defer()
        assert itr.guild
        group = group_roles_of(itr.guild.id)
        owned = sorted(
            (r for r in await self.bot.db.roles.get(itr.user.id) if r in group),
            key=group.index,
        )
        embed = discord.Embed(
            title="Inventory",
            description="\n".join(f"<@&{r}>" for r in owned) or "Empty",
            color=itr.user.color,
        )
        embed.set_footer(text=NOTICE)
        await itr.followup.send(embed=embed, allowed_mentions=NO_MENTIONS, silent=True)


async def setup(bot: dBot) -> None:
    await bot.add_cog(Role(bot))
