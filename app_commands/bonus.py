from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from app_commands.autocomplete.bonus import artist_autocomplete
from static.dConsts import GAMES
from static.dServices import sheetService
from static.dTypes import GameDetails


class Bonus(commands.GroupCog, name="bonus"):
    GAME_CHOICES = [
        app_commands.Choice(name=game["name"], value=key) for key, game in GAMES.items()
    ]

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="add",
        description=(
            "Add an artist to the bonus ping list (1 hour "
            "before bonus starts, 1 day 1 hour before bonus ends)"
        ),
    )
    @app_commands.autocomplete(artist_name=artist_autocomplete)
    @app_commands.choices(game=GAME_CHOICES)
    async def bonus_add(
        self, itr: discord.Interaction, game: app_commands.Choice[str], artist_name: str
    ):
        await self._handle_bonus_command(itr, game.value, artist_name, itr.command.name)

    @app_commands.command(
        name="remove", description="Remove an artist from the bonus ping list"
    )
    @app_commands.autocomplete(artist_name=artist_autocomplete)
    @app_commands.choices(game=GAME_CHOICES)
    async def bonus_remove(
        self, itr: discord.Interaction, game: app_commands.Choice[str], artist_name: str
    ):
        await self._handle_bonus_command(itr, game.value, artist_name, itr.command.name)

    @staticmethod
    async def _handle_bonus_command(
        itr: discord.Interaction, game_key: str, artist_name: str, operation: str
    ):
        await itr.response.defer(ephemeral=True)
        game_details = GAMES[game_key]
        ping_data = Bonus._get_ping_data(game_details)
        user_id = str(itr.user.id)
        artist_column_index = game_details["pingColumns"].index("artist_name")
        users_column_index = game_details["pingColumns"].index("users")

        for i, row in enumerate(ping_data, start=1):
            _artist_name = row[artist_column_index]
            if _artist_name.lower() == artist_name.lower():
                users = row[users_column_index].split(",")

                if not (
                    message_prefix := Bonus._update_artist_ping_list(
                        operation, user_id, users
                    )
                ):
                    await itr.followup.send("Internal error.")
                    return

                if not message_prefix.startswith("Already"):
                    Bonus._update_ping_data(game_details, users, i)

                await itr.followup.send(f"{message_prefix} {_artist_name} ping list!")
                return

        await itr.followup.send(
            f"{artist_name} is not a valid artist for {game_details["name"]}"
        )

    @staticmethod
    def _get_ping_data(game_details: GameDetails) -> list[list[str]]:
        result = (
            sheetService.values()
            .get(spreadsheetId=game_details["pingId"], range=game_details["pingRange"])
            .execute()
        )
        return result.get("values", [])

    @staticmethod
    def _update_artist_ping_list(
        operation: str, user_id: str, users: list[str]
    ) -> Optional[str]:
        if operation == "add":
            if user_id not in users:
                users.append(user_id)
                message_prefix = "Added to"
            else:
                message_prefix = "Already in"
        elif operation == "remove":
            if user_id in users:
                users.remove(user_id)
                message_prefix = "Removed from"
            else:
                message_prefix = "Already not in"
        else:
            message_prefix = None

        return message_prefix

    @staticmethod
    def _update_ping_data(
        game_details: GameDetails, users: list[str], artist_index: int
    ):
        sheetService.values().update(
            spreadsheetId=game_details["pingId"],
            range=f"{game_details["pingWrite"]}{artist_index}",
            valueInputOption="RAW",
            body={"values": [[",".join(users)]]},
        ).execute()


async def setup(bot: commands.Bot):
    await bot.add_cog(Bonus(bot))
