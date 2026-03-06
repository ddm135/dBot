# mypy: disable-error-code="assignment"
# pyright: reportAssignmentType=false, reportTypedDictNotRequiredAccess=false

import math
import re
from itertools import groupby
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Literal

import discord
from discord import app_commands
from discord.ext import commands

from statics.consts import GAMES, Data

from .autocompletes import artist_autocomplete
from .commons import MAX_POSITIONS, STEP, bonus_top_embeds
from .embeds import BonusListEmbed, BonusPingsEmbed
from .views import BonusListView, BonusTopView

if TYPE_CHECKING:
    from dBot import dBot
    from helpers.google_sheets import GoogleSheets
    from helpers.superstar import SuperStar
    from tasks.data_sync import DataSync


class Bonus(commands.GroupCog, name="bonus", description="Add/Remove Bonus Pings"):
    GAME_CHOICES = [
        app_commands.Choice(name=game_details["name"], value=game)
        for game, game_details in GAMES.items()
        if {"bonus", "ping"} <= set(game_details)
    ]
    FILTERED_GAME_CHOICES = [
        choice for choice in GAME_CHOICES if {"base_score"} <= set(GAMES[choice.value])
    ]

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    @app_commands.command(name="list")
    @app_commands.choices(game_choice=GAME_CHOICES)
    @app_commands.autocomplete(artist_choice=artist_autocomplete)
    @app_commands.rename(game_choice="game", artist_choice="artist")
    async def bonus_list(
        self,
        itr: discord.Interaction["dBot"],
        game_choice: app_commands.Choice[str],
        artist_choice: str | None = None,
        time: Literal["current week", "next week", "current month"] | None = None,
        live_theme_bonus: int | None = None,
    ) -> None:
        """View bonus information, sorted by end date then start date

        Parameters
        -----------
        game_choice: Choice[:class:`str`]
            Game
        artist_choice: Optional[:class:`str`]
            Artist/Album
        time: Optional[:class:`BonusPeriod`]
            Time Period
        live_theme_bonus: Optional[:class:`int`]
            Live Theme Bonus (configure default with /bonus live_theme set)
        """

        await itr.response.defer()
        live_theme_bonus = (
            live_theme_bonus or self.bot.live_theme[game_choice.value][str(itr.user.id)]
        )
        if (
            live_theme_bonus < 0
            or live_theme_bonus > self.bot.live_theme[game_choice.value]["max"]
        ):
            return await itr.followup.send("Invalid live theme bonus amount.")

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
            icon = self.bot.artist[game_choice.value][artist_choice]["emblem"]

        cog: "SuperStar" = self.bot.get_cog("SuperStar")
        results = cog.get_period_bonuses(
            game_choice.value, artists, time, live_theme_bonus
        )
        if not results:
            return await itr.followup.send("Invalid time period.")
        period_bonuses, first_date, current_date, last_date = results

        period_bonuses.sort(key=lambda x: (x["bonusEnd"], x["bonusStart"]))
        first_available_index = 0
        for i, _bonus in enumerate(period_bonuses):
            if _bonus["bonusEnd"] >= current_date:
                first_available_index = i
                break

        default_page = first_available_index // STEP + 1
        max_page = math.ceil(len(period_bonuses) / STEP) or 1

        msg = await itr.followup.send(
            embed=BonusListEmbed(
                game_choice.value,
                artist_choice,
                period_bonuses,
                first_date,
                current_date,
                last_date,
                icon,
                default_page,
                max_page,
            ),
            files=(
                [discord.File(icon, filename="icon.png")]
                if isinstance(icon, Path)
                else []
            ),
            wait=True,
        )
        view = BonusListView(
            msg,
            game_choice.value,
            artist_choice,
            first_date,
            current_date,
            last_date,
            period_bonuses,
            itr.user,
            icon,
            default_page,
            max_page,
        )
        await msg.edit(view=view)

    @app_commands.command(name="top")
    @app_commands.choices(game_choice=FILTERED_GAME_CHOICES)
    @app_commands.rename(game_choice="game")
    async def bonus_top(
        self,
        itr: discord.Interaction["dBot"],
        game_choice: app_commands.Choice[str],
        live_theme_bonus: int | None = None,
    ) -> None:
        """View bonuses that yield the highest score with
        max Top 5 score and groups of the week

        Parameters
        -----------
        game_choice: Choice[:class:`str`]
            Game
        live_theme_bonus: Optional[:class:`int`]
            Live Theme Bonus (configure default with /bonus live_theme set)
        """

        await itr.response.defer()
        live_theme_bonus = (
            live_theme_bonus or self.bot.live_theme[game_choice.value][str(itr.user.id)]
        )
        if (
            live_theme_bonus < 0
            or live_theme_bonus > self.bot.live_theme[game_choice.value]["max"]
        ):
            return await itr.followup.send("Invalid live theme bonus amount.")

        bonus_data = self.bot.bonus[game_choice.value]
        icon = self.bot.basic[game_choice.value]["iconUrl"]

        cog: "SuperStar" = self.bot.get_cog("SuperStar")
        results = cog.get_period_bonuses(
            game_choice.value, bonus_data.keys(), "current week", live_theme_bonus
        )
        if not results:
            return await itr.followup.send("Invalid time period.")
        period_bonuses, _, current_date, last_date = results

        period_bonuses.sort(key=lambda x: list(bonus_data).index(x["artist"]))
        grouped_bonuses = {
            artist_name: sorted(
                bonuses, key=lambda x: (-x["maxScore"], x["bonusEnd"], x["bonusStart"])
            )
            for artist_name, bonuses in groupby(
                period_bonuses, key=lambda x: x["artist"]
            )
        }
        sorted_bonuses = dict(
            sorted(grouped_bonuses.items(), key=lambda x: -x[1][0]["maxScore"])
        )
        highest_bonuses = {
            artist_name: [
                bonus
                for bonus in bonuses
                if bonus["maxScore"] == bonuses[0]["maxScore"]
            ]
            for artist_name, bonuses in sorted_bonuses.items()
        }

        all_scores = {
            artist_name: details["score"] + live_theme_bonus
            for artist_name, details in self.bot.artist[game_choice.value].items()
        }
        for artist_name, bonuses in highest_bonuses.items():
            all_scores[artist_name] = bonuses[0]["maxScore"]
        sorted_scores = dict(sorted(all_scores.items(), key=lambda x: -x[1]))

        score_position = 1
        remaining_positions = MAX_POSITIONS
        highest_score = 0
        total_score = 0
        highest_scores: dict[int, list] = {}
        for artist_name, score in sorted_scores.items():
            if score < highest_score:
                score_position += len(highest_scores[highest_score])
            if score_position > MAX_POSITIONS:
                break

            highest_score = score
            highest_scores.setdefault(score, []).append(artist_name)
            if remaining_positions:
                total_score += score
                remaining_positions -= 1

        embeds = bonus_top_embeds(
            game_choice.value, highest_bonuses, current_date, last_date, icon
        )

        msg = await itr.followup.send(
            embed=embeds[0],
            files=(
                [discord.File(icon, filename="icon.png")]
                if isinstance(icon, Path)
                else []
            ),
            wait=True,
        )
        view = BonusTopView(
            msg,
            game_choice.value,
            current_date,
            last_date,
            sorted_bonuses,
            highest_bonuses,
            embeds,
            highest_scores,
            total_score,
            itr.user,
            icon,
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
            Artist/Album
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
            Artist/Album
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
            Game
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

    bonus_live_theme = app_commands.Group(
        name="live_theme",
        description="Manage live theme bonus score",
    )

    @bonus_live_theme.command(name="set")
    @app_commands.choices(game_choice=FILTERED_GAME_CHOICES)
    @app_commands.rename(game_choice="game")
    async def live_theme_set(
        self,
        itr: discord.Interaction["dBot"],
        game_choice: app_commands.Choice[str],
        live_theme_bonus: int,
    ) -> None:
        """Set the default Live Theme Bonus amount
        when using bonus commands

        Parameters
        -----------
        game_choice: Choice[:class:`str`]
            Game
        live_theme_bonus: :class:`int`
            Live Theme Bonus
        """

        await itr.response.defer(ephemeral=True)
        if (
            live_theme_bonus < 0
            or live_theme_bonus > self.bot.live_theme[game_choice.value]["max"]
        ):
            return await itr.followup.send("Invalid live theme bonus amount.")

        self.bot.live_theme[game_choice.value][str(itr.user.id)] = live_theme_bonus
        cog: "DataSync" = self.bot.get_cog("DataSync")
        cog.save_data(Data.LIVE_THEME)
        return await itr.followup.send(
            f"{GAMES[game_choice.value]["name"]} Live Theme Bonus "
            f"has been set to {live_theme_bonus:,}!"
        )

    async def handle_bonus_command(
        self,
        itr: discord.Interaction["dBot"],
        game: str,
        artist_name: str,
        operation: str,
    ) -> None:
        await itr.response.defer(ephemeral=True)
        user_id = str(itr.user.id)

        cog: "GoogleSheets" = self.bot.get_cog("GoogleSheets")
        game_details = GAMES[game]
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
