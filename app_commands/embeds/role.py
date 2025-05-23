import discord

from app_commands.commons.role import NOTICE


class RoleSetEmbed(discord.Embed):
    def __init__(
        self,
        target: discord.Role,
        add: tuple[discord.Role, ...],
        remove: tuple[discord.Role, ...],
    ) -> None:
        description = ""
        if add:
            description += "**Applied**\n"
            description += "\n".join(f"{role.mention}" for role in reversed(add))

            if remove:
                description += "\n\n"
        if remove:
            description += "**Stored**\n"
            description += "\n".join(f"{role.mention}" for role in reversed(remove))

        super().__init__(
            title="Changes",
            description=description or "None",
            color=target.color,
        )
        self.set_footer(text=NOTICE)


class RoleInventoryEmbed(discord.Embed):
    def __init__(
        self,
        user: discord.User | discord.Member,
        roles: list[int],
    ) -> None:
        super().__init__(
            title="Inventory",
            description=(
                "\n".join(f"<@&{role}>" for role in roles) if roles else "Empty"
            ),
            color=user.color,
        )
        self.set_footer(text=NOTICE)
