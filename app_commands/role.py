import discord
from discord import app_commands
from discord.ext import commands

from app_commands.autocomplete.role import (
    role_add_autocomplete,
    role_remove_autocomplete,
)
from static.dConsts import TEST_GUILD


class Role(commands.GroupCog, name="role"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="add")
    @app_commands.autocomplete(role=role_add_autocomplete)
    @app_commands.guilds(TEST_GUILD)
    async def role_add(self, itr: discord.Interaction, role: str) -> None:
        print(role)
        role = discord.utils.get(itr.guild.roles, id=int(role))
        await itr.user.add_roles(role)
        await itr.response.send_message(f"Added <@&{role.id}>!", ephemeral=True)
        
    @app_commands.command(name="remove")
    @app_commands.autocomplete(role=role_remove_autocomplete)
    @app_commands.guilds(TEST_GUILD)
    async def role_remove(self, itr: discord.Interaction, role: str) -> None:
        print(role)
        role = discord.utils.get(itr.guild.roles, id=int(role))
        await itr.user.remove_roles(role)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Role(bot))
