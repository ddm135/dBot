# mypy: disable-error-code="assignment"
# pyright: reportAssignmentType=false, reportTypedDictNotRequiredAccess=false

import math
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Literal

import discord
from discord import app_commands
from discord.ext import commands

from statics.consts import BONUS_OFFSET, GAMES

from .autocompletes import artist_autocomplete
from .commons import STEP
from .embeds import BonusesEmbed, BonusPingsEmbed
from .types import BonusDict
from .views import BonusView

if TYPE_CHECKING:
    from dBot import dBot
    from helpers.google_sheets import GoogleSheets


class Bonus(commands.GroupCog, name="bonus", description="Add/Remove Bonus Pings"):
    GAME_CHOICES = [
        app_commands.Choice(name=game_details["name"], value=game)
        for game, game_details in GAMES.items()
        if {"bonus", "ping"} <= set(game_details)
    ]

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    @app_commands.command()
    @app_commands.choices(game_choice=GAME_CHOICES)
    @app_commands.autocomplete(artist_choice=artist_autocomplete)
    @app_commands.rename(game_choice="game", artist_choice="artist")
    async def list(
        self,
        itr: discord.Interaction["dBot"],
        game_choice: app_commands.Choice[str],
        artist_choice: str | None = None,
        time: Literal["current week", "next week", "current month"] | None = None,
    ) -> None:
        """View bonus information, sorted by end date then start date

        Parameters
        -----------
        game_choice: Choice[:class:`str`]
            Game
        artist_choice: Optional[:class:`str`]
            Artist Name
        time: Optional[:class:`BonusPeriod`]
            Time Period
        """

        await itr.response.defer()
        game_details = GAMES[game_choice.value]
        bonus_data = self.bot.bonus[game_choice.value]
        artists: Iterable[str]
        icon: str | Path | None
        if not artist_choice:
            artists = bonus_data.keys()
            icon = self.bot.basic[game_choice.value]["iconUrl"]
        else:
            if artist_choice not in bonus_data:
                return await itr.followup.send("Artist not found.")
            artists = [artist_choice]
            icon = self.bot.emblem[game_choice.value][artist_choice]

        timezone = game_details["timezone"]
        bonus_columns = game_details["bonus"]["columns"]
        current_date = datetime.now(tz=timezone).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        match time:
            case None:
                first_date = current_date.replace(day=1, month=1)
                last_date = current_date.replace(day=31, month=12)
            case "current week":
                first_date = current_date - timedelta(days=current_date.weekday())
                last_date = first_date + timedelta(days=7)
            case "next week":
                first_date = (
                    current_date
                    - timedelta(days=current_date.weekday())
                    + timedelta(days=7)
                )
                last_date = first_date + timedelta(days=7)
            case "current month":
                first_date = current_date.replace(day=1)
                if current_date.month == 12:
                    last_date = first_date.replace(day=31)
                else:
                    last_date = current_date.replace(
                        month=current_date.month + 1, day=1
                    ) - timedelta(days=1)
            case _:
                return await itr.followup.send("Invalid time period.")
        tracking_date = first_date

        member_name_index = bonus_columns.index("member_name")
        bonus_start_index = bonus_columns.index("bonus_start")
        bonus_end_index = bonus_columns.index("bonus_end")
        bonus_amount_index = bonus_columns.index("bonus_amount")
        period_bonuses = []

        while tracking_date <= last_date:
            for artist in artists:
                artist_name = (
                    artist.replace(r"*", r"\*")
                    .replace(r"_", r"\_")
                    .replace(r"`", r"\`")
                )
                birthday_bonuses = []
                album_bonuses = []
                last_birthday_start = None
                last_birthday_end = None
                next_birthday_start = None
                next_birthday_end = None
                for bonus in bonus_data[artist]:
                    start_date = bonus[bonus_start_index]
                    end_date = bonus[bonus_end_index]

                    if start_date < tracking_date and bonus[member_name_index]:
                        last_birthday_start = start_date

                    if end_date < tracking_date and bonus[member_name_index]:
                        last_birthday_end = end_date + BONUS_OFFSET

                    if (
                        not next_birthday_start
                        and tracking_date < start_date
                        and bonus[member_name_index]
                    ):
                        next_birthday_start = start_date - BONUS_OFFSET

                    if (
                        not next_birthday_end
                        and tracking_date < end_date
                        and bonus[member_name_index]
                    ):
                        next_birthday_end = end_date

                    if start_date <= tracking_date <= end_date:
                        if bonus[member_name_index]:
                            birthday_bonuses.append(bonus)
                        else:
                            album_bonuses.append(bonus)

                birthday_members = ""
                birthday_total = 0
                birthday_starts = ()
                birthday_ends = ()
                if birthday_bonuses:
                    birthday_zip = tuple(zip(*birthday_bonuses))
                    birthday_members = (
                        " + ".join(birthday_zip[member_name_index])
                        .replace(r"*", r"\*")
                        .replace(r"_", r"\_")
                        .replace(r"`", r"\`")
                    )
                    birthday_amounts = birthday_zip[bonus_amount_index]
                    for amt in birthday_amounts:
                        birthday_total += amt

                    birthday_starts = birthday_zip[bonus_start_index]
                    birthday_ends = birthday_zip[bonus_end_index]

                birthday_start = max(
                    (
                        x
                        for x in (
                            *birthday_starts,
                            last_birthday_end,
                            last_birthday_start,
                        )
                        if x
                    ),
                    default=None,
                )

                birthday_end = min(
                    (
                        x
                        for x in (
                            *birthday_ends,
                            next_birthday_end,
                            next_birthday_start,
                        )
                        if x
                    ),
                    default=None,
                )

                if (
                    birthday_bonuses
                    and birthday_start
                    and birthday_end
                    and birthday_total > 0
                    and (
                        birthday_end == tracking_date or birthday_start == tracking_date
                    )
                ):
                    bonus_dict = BonusDict(
                        artist=artist_name,
                        members=birthday_members,
                        song=None,
                        bonusStart=birthday_start,
                        bonusEnd=birthday_end,
                        bonusAmount=birthday_total,
                    )
                    if bonus_dict not in period_bonuses:
                        period_bonuses.append(bonus_dict)

                for bonus in album_bonuses:
                    start_date = bonus[bonus_start_index]
                    end_date = bonus[bonus_end_index]

                    song_start = max(x for x in (start_date, birthday_start) if x)
                    song_end = min(x for x in (end_date, birthday_end) if x)

                    if song_start != tracking_date and song_end != tracking_date:
                        continue

                    song_total = birthday_total + bonus[bonus_amount_index]
                    song_name = (
                        bonus[bonus_columns.index("song_name")]
                        .replace(r"*", r"\*")
                        .replace(r"_", r"\_")
                        .replace(r"`", r"\`")
                    )
                    bonus_dict = BonusDict(
                        artist=artist_name,
                        members=None,
                        song=song_name,
                        bonusStart=song_start,
                        bonusEnd=song_end,
                        bonusAmount=song_total,
                    )
                    if bonus_dict not in period_bonuses:
                        period_bonuses.append(bonus_dict)

            tracking_date += BONUS_OFFSET

        period_bonuses.sort(key=lambda x: (x["bonusEnd"], x["bonusStart"]))
        first_available_index = 0
        for i, _bonus in enumerate(period_bonuses):
            if _bonus["bonusEnd"] >= current_date:
                first_available_index = i
                break

        default_page = first_available_index // STEP + 1
        max_page = math.ceil(len(period_bonuses) / STEP) or 1

        msg = await itr.followup.send(
            embed=BonusesEmbed(
                game_details,
                artist_choice,
                period_bonuses,
                first_date,
                last_date,
                current_date,
                icon,
                default_page,
                max_page,
            ),
            files=[discord.File(icon)] if isinstance(icon, Path) else [],
            wait=True,
        )
        view = BonusView(
            msg,
            game_details,
            artist_choice,
            first_date,
            last_date,
            current_date,
            period_bonuses,
            itr.user,
            icon,
            default_page,
            max_page,
        )
        await msg.edit(view=view)

    bonus_ping = app_commands.Group(
        name="ping",
        description="Get notified when bonuses start or end",
    )

    @bonus_ping.command(name="add")
    @app_commands.choices(game_choice=GAME_CHOICES)
    @app_commands.autocomplete(artist_choice=artist_autocomplete)
    @app_commands.rename(game_choice="game", artist_choice="artist")
    async def bonus_ping_add(
        self,
        itr: discord.Interaction["dBot"],
        game_choice: app_commands.Choice[str],
        artist_choice: str,
    ) -> None:
        """Add an artist to your bonus ping list
        (1 hour before bonus starts,
        1 day 1 hour before bonus ends)

        Parameters
        -----------
        game_choice: Choice[:class:`str`]
            Game
        artist_choice: :class:`str`
            Artist Name
        """

        assert itr.command
        await self.handle_bonus_command(
            itr, game_choice.value, artist_choice, itr.command.name
        )

    @bonus_ping.command(name="remove")
    @app_commands.choices(game_choice=GAME_CHOICES)
    @app_commands.autocomplete(artist_choice=artist_autocomplete)
    @app_commands.rename(game_choice="game", artist_choice="artist")
    async def bonus_ping_remove(
        self,
        itr: discord.Interaction["dBot"],
        game_choice: app_commands.Choice[str],
        artist_choice: str,
    ) -> None:
        """Remove an artist from your bonus ping list

        Parameters
        -----------
        game_choice: Choice[:class:`str`]
            Game
        artist_choice: :class:`str`
            Artist Name
        """

        assert itr.command
        await self.handle_bonus_command(
            itr, game_choice.value, artist_choice, itr.command.name
        )

    @bonus_ping.command(name="list")
    @app_commands.choices(game_choice=GAME_CHOICES)
    @app_commands.rename(game_choice="game")
    async def bonus_ping_list(
        self,
        itr: discord.Interaction["dBot"],
        game_choice: app_commands.Choice[str] | None = None,
    ) -> None:
        """List your bonus ping list

        Parameters
        -----------
        game_choice: Optional[Choice[:class:`str`]]
            Game. If left empty, will list all games.
        """

        await itr.response.defer(ephemeral=True)
        games = [game_choice] if game_choice else self.GAME_CHOICES

        await itr.user.send("## Bonus Ping List")

        cog: "GoogleSheets" = self.bot.get_cog("GoogleSheets")
        for game in games:
            game_details = GAMES[game.value]
            ping_data = await cog.get_sheet_data(
                game_details["ping"]["spreadsheetId"], game_details["ping"]["range"]
            )
            icon = self.bot.basic[game.value]["iconUrl"]
            embed = BonusPingsEmbed(game.value, ping_data, str(itr.user.id), icon)
            await itr.user.send(embed=embed, silent=True)

        return await itr.followup.send(
            "Check your DMs for the list of artists you are pinged for!"
        )

    async def handle_bonus_command(
        self,
        itr: discord.Interaction["dBot"],
        game_key: str,
        artist_name: str,
        operation: str,
    ) -> None:
        await itr.response.defer(ephemeral=True)
        user_id = str(itr.user.id)

        cog: "GoogleSheets" = self.bot.get_cog("GoogleSheets")
        game_details = GAMES[game_key]
        ping_columns = game_details["ping"]["columns"]
        artist_name_index = ping_columns.index("artist_name")
        users_index = ping_columns.index("users")
        ping_data = await cog.get_sheet_data(
            game_details["ping"]["spreadsheetId"], game_details["ping"]["range"]
        )

        for i, row in enumerate(ping_data, start=1):
            _artist_name = row[artist_name_index]
            if _artist_name.lower() != artist_name.lower():
                continue

            users = set(row[users_index].split(","))
            users.discard("")

            if operation == "add":
                if user_id not in users:
                    users.add(user_id)
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

            if not message_prefix:
                return await itr.followup.send("Internal error.")

            if not message_prefix.startswith("Already"):
                await cog.update_sheet_data(
                    game_details["ping"]["spreadsheetId"],
                    f"{re.split(r"\d+:", game_details["ping"]["range"])[0]}{i}",
                    [[",".join(users)]],
                )

            return await itr.followup.send(
                f"{message_prefix} {_artist_name} ping list!"
            )

        await itr.followup.send(
            f"{artist_name} is not a valid artist for {game_details["name"]}"
        )


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Bonus(bot))
