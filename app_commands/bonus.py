from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands

from app_commands.autocomplete.bonus import _ping_preprocess, artist_autocomplete
from static.dConsts import GAMES
from static.dHelpers import update_sheet_data
from static.dTypes import GameDetails

if TYPE_CHECKING:
    from dBot import dBot


class Bonus(commands.GroupCog, name="bonus", description="Add/Remove Bonus Pings"):
    GAME_CHOICES = [
        app_commands.Choice(name=game["name"], value=key) for key, game in GAMES.items()
    ]

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    @app_commands.command(name="add")
    @app_commands.autocomplete(artist_name=artist_autocomplete)
    @app_commands.choices(game=GAME_CHOICES)
    @app_commands.rename(artist_name="artist")
    async def bonus_add(
        self,
        itr: discord.Interaction["dBot"],
        game: app_commands.Choice[str],
        artist_name: str,
    ) -> None:
        """Add an artist to your bonus ping list
        (1 hour before bonus starts,
        1 day 1 hour before bonus ends)

        Parameters
        -----------
        game: Choice[:class:`str`]
            Game
        artist_name: :class:`str`
            Artist Name
        """

        assert itr.command
        await self._handle_bonus_command(itr, game.value, artist_name, itr.command.name)

    @app_commands.command(name="remove")
    @app_commands.autocomplete(artist_name=artist_autocomplete)
    @app_commands.choices(game=GAME_CHOICES)
    @app_commands.rename(artist_name="artist")
    async def bonus_remove(
        self,
        itr: discord.Interaction["dBot"],
        game: app_commands.Choice[str],
        artist_name: str,
    ) -> None:
        """Remove an artist from your bonus ping list

        Parameters
        -----------
        game: Choice[:class:`str`]
            Game
        artist_name: :class:`str`
            Artist Name
        """

        assert itr.command
        await self._handle_bonus_command(itr, game.value, artist_name, itr.command.name)

    async def _handle_bonus_command(
        self,
        itr: discord.Interaction["dBot"],
        game_key: str,
        artist_name: str,
        operation: str,
    ) -> None:
        await itr.response.defer(ephemeral=True)
        user_id = str(itr.user.id)
        (
            game_details,
            ping_data,
            artist_name_index,
            users_index,
        ) = _ping_preprocess(game_key)

        for i, row in enumerate(ping_data, start=1):
            _artist_name = row[artist_name_index]
            if _artist_name.lower() == artist_name.lower():
                users = row[users_index].split(",")
                users.remove("") if "" in users else None

                if not (
                    message_prefix := self._update_artist_ping_list(
                        operation, user_id, users
                    )
                ):
                    return await itr.followup.send("Internal error.")

                if not message_prefix.startswith("Already"):
                    self._update_ping_data(game_details, users, i)

                return await itr.followup.send(
                    f"{message_prefix} {_artist_name} ping list!"
                )

        await itr.followup.send(
            f"{artist_name} is not a valid artist for {game_details["name"]}"
        )

    def _update_artist_ping_list(
        self,
        operation: str,
        user_id: str,
        users: list[str],
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

    def _update_ping_data(
        self,
        game_details: GameDetails,
        users: list[str],
        artist_index: int,
    ) -> None:
        update_sheet_data(
            game_details["pingId"],
            f"{game_details["pingWrite"]}{artist_index}",
            parse_input=False,
            data=[[",".join(users)]],
        )


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Bonus(bot))
