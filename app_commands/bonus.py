import math
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands

from app_commands.autocomplete.bonus import _ping_preprocess, artist_autocomplete
from statics.consts import GAMES, ONE_DAY
from statics.helpers import update_sheet_data

if TYPE_CHECKING:
    from dBot import dBot
    from statics.types import GameDetails

STEP = 5


class Bonus(commands.GroupCog, name="bonus", description="Add/Remove Bonus Pings"):
    GAME_CHOICES = [
        app_commands.Choice(name=game["name"], value=key)
        for key, game in GAMES.items()
        if game["pingId"]
    ]

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    @app_commands.command()
    @app_commands.choices(game=GAME_CHOICES)
    async def week(
        self,
        itr: discord.Interaction["dBot"],
        game: app_commands.Choice[str],
    ) -> None:
        """View bonus information for the current week,
        sorted by end date then start date

        Parameters
        -----------
        game_choice: Choice[:class:`str`]
            Game
        """

        await itr.response.defer()
        if not self.bot.bonus_data_ready:
            return await itr.followup.send(
                "Bonus data synchronization in progress, feature unavailable."
            )

        game_details = GAMES[game.value]
        timezone = game_details["timezone"]
        bonus_columns = game_details["bonusColumns"]

        current_date = datetime.now(tz=timezone).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        first_date = current_date - timedelta(days=current_date.weekday())
        tracking_date = first_date
        last_date = tracking_date + timedelta(days=7)

        member_name_index = bonus_columns.index("member_name")
        bonus_start_index = bonus_columns.index("bonus_start")
        bonus_end_index = bonus_columns.index("bonus_end")
        bonus_amount_index = bonus_columns.index("bonus_amount")

        bonus_data = self.bot.bonus_data[game.value]
        artists = bonus_data.keys()
        full_bonuses = []

        while tracking_date <= last_date:
            for artist in artists:
                artist_name = artist.replace(r"*", r"\*").replace(r"_", r"\_")
                birthday_bonuses: list[list[Any]] = []
                album_bonuses: list[list[Any]] = []
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
                        last_birthday_end = end_date + ONE_DAY

                    if (
                        not next_birthday_start
                        and tracking_date < start_date
                        and bonus[member_name_index]
                    ):
                        next_birthday_start = start_date - ONE_DAY

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
                        if x is not None
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
                        if x is not None
                    ),
                    default=None,
                )

                start_check = last_birthday_end != tracking_date
                end_check = next_birthday_start != tracking_date

                if (
                    birthday_bonuses
                    and birthday_start
                    and birthday_end
                    and (
                        (birthday_end == tracking_date and end_check)
                        or (birthday_start == tracking_date and start_check)
                    )
                ):
                    bonus_dict = {
                        "artist": artist_name,
                        "members": birthday_members,
                        "song": None,
                        "bonus_start": birthday_start,
                        "bonus_end": birthday_end,
                        "bonus_amount": birthday_total,
                    }
                    if bonus_dict not in full_bonuses:
                        full_bonuses.append(bonus_dict)

                for bonus in album_bonuses:
                    start_date = bonus[bonus_start_index]
                    end_date = bonus[bonus_end_index]

                    song_start = max(
                        x for x in (start_date, birthday_start) if x is not None
                    )
                    song_end = min(x for x in (end_date, birthday_end) if x is not None)

                    if (song_start == tracking_date and start_check) or (
                        song_end == tracking_date and end_check
                    ):
                        song_total = birthday_total + bonus[bonus_amount_index]
                        song_name = (
                            bonus[bonus_columns.index("song_name")]
                            .replace(r"*", r"\*")
                            .replace(r"_", r"\_")
                        )
                        bonus_dict = {
                            "artist": artist_name,
                            "members": None,
                            "song": song_name,
                            "bonus_start": song_start,
                            "bonus_end": song_end,
                            "bonus_amount": song_total,
                        }
                        if bonus_dict not in full_bonuses:
                            full_bonuses.append(bonus_dict)
            tracking_date += ONE_DAY

        full_bonuses.sort(key=lambda x: (x["bonus_end"], x["bonus_start"]))
        first_available_index = 0
        for i, _bonus in enumerate(full_bonuses):
            if _bonus["bonus_end"] >= current_date:
                first_available_index = i
                break

        default_page = first_available_index // STEP + 1
        max_page = math.ceil(len(full_bonuses) / STEP) or 1

        msg = await itr.followup.send(
            embed=create_embed(
                game_details,
                full_bonuses,
                first_date,
                last_date,
                current_date,
                default_page,
                max_page,
            ),
            wait=True,
        )
        view = BonusView(
            msg,
            game_details,
            first_date,
            last_date,
            current_date,
            full_bonuses,
            default_page,
            max_page,
        )
        await msg.edit(view=view)

    bonus_ping = app_commands.Group(
        name="ping",
        description="Get notified when bonuses start or end",
    )

    @bonus_ping.command(name="add")
    @app_commands.autocomplete(artist_name=artist_autocomplete)
    @app_commands.choices(game=GAME_CHOICES)
    @app_commands.rename(artist_name="artist")
    async def bonus_ping_add(
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

    @bonus_ping.command(name="remove")
    @app_commands.autocomplete(artist_name=artist_autocomplete)
    @app_commands.choices(game=GAME_CHOICES)
    @app_commands.rename(artist_name="artist")
    async def bonus_ping_remove(
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

    @bonus_ping.command(name="list")
    @app_commands.choices(game=GAME_CHOICES)
    async def bonus_ping_list(
        self,
        itr: discord.Interaction["dBot"],
        game: app_commands.Choice[str] | None = None,
    ) -> None:
        """List your bonus ping list

        Parameters
        -----------
        game: Optional[Choice[:class:`str`]]
            Game. If left empty, will list all games.
        """

        await itr.response.defer(ephemeral=True)
        user_id = str(itr.user.id)

        if game is None:
            games = self.GAME_CHOICES
        else:
            games = [game]

        await itr.user.send("## Bonus Ping List")
        for game in games:
            (
                game_details,
                ping_data,
                artist_name_index,
                users_index,
            ) = _ping_preprocess(game.value)

            description = ""
            for row in ping_data:
                _artist_name = row[artist_name_index]
                users = row[users_index].split(",")
                users.remove("") if "" in users else None

                if user_id in users:
                    description += f"- {_artist_name}\n"

            if not description:
                description = "None"
            else:
                description = description[:-1]

            embed = discord.Embed(
                title=f"{game_details['name']}",
                description=description,
                color=game_details["color"],
            )
            await itr.user.send(embed=embed, silent=True)

        return await itr.followup.send(
            "Check your DMs for the list of artists you are pinged for!"
        )

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
    ) -> str | None:
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
        game_details: "GameDetails",
        users: list[str],
        artist_index: int,
    ) -> None:
        update_sheet_data(
            game_details["pingId"],
            f"{game_details["pingWrite"]}{artist_index}",
            parse_input=False,
            data=[[",".join(users)]],
        )


class BonusView(discord.ui.View):

    def __init__(
        self,
        message: discord.Message,
        game_details: "GameDetails",
        first_date: datetime,
        last_date: datetime,
        current_date: datetime,
        bonuses: list[dict],
        current_page: int,
        max_page: int,
    ) -> None:
        self.message = message
        self.game_details = game_details
        self.bonuses = bonuses
        self.first_date = first_date
        self.last_date = last_date
        self.current_date = current_date
        self.current_page = current_page
        self.max_page = max_page
        super().__init__(timeout=60)

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await self.message.edit(view=self)

    async def update_message(self) -> None:
        await self.message.edit(
            embed=create_embed(
                self.game_details,
                self.bonuses,
                self.first_date,
                self.last_date,
                self.current_date,
                self.current_page,
                self.max_page,
            ),
            view=self,
        )

    @discord.ui.button(label="Previous Page", style=discord.ButtonStyle.secondary)
    async def previous_page(
        self, itr: discord.Interaction["dBot"], button: discord.ui.Button
    ) -> None:
        await itr.response.defer()
        self.current_page -= 1
        if self.current_page < 1:
            self.current_page = self.max_page
        await self.update_message()

    @discord.ui.button(label="Next Page", style=discord.ButtonStyle.primary)
    async def next_page(
        self, itr: discord.Interaction["dBot"], button: discord.ui.Button
    ) -> None:
        await itr.response.defer()
        self.current_page += 1
        if self.current_page > self.max_page:
            self.current_page = 1
        await self.update_message()


def create_embed(
    game_details: "GameDetails",
    bonuses: list[dict],
    first_date: datetime,
    last_date: datetime,
    current_date: datetime,
    current_page: int,
    max_page: int,
) -> discord.Embed:
    end = current_page * STEP
    start = end - STEP
    filtered_bonuses = bonuses[start:end]
    embed = discord.Embed(
        title=(
            f"{game_details["name"]} {current_date.strftime("%G-W%V")} Bonuses "
            f"({first_date.strftime('%B %d')} - {last_date.strftime('%B %d')})"
        ).replace(" 0", " "),
        color=game_details["color"],
    )
    for bonus in filtered_bonuses:
        embed.add_field(
            name=(
                f"{("~~" if bonus["bonus_end"] < current_date
                    else "" if bonus["bonus_start"] > current_date
                    else ":white_check_mark: ")}"
                f"**{bonus["artist"]}**"
                f"{(f" {bonus["members"]}"
                    if bonus["members"] and bonus["artist"] != bonus["members"]
                    else "")}: "
                f"{bonus["song"] if bonus["song"] else "All Songs :birthday:"}"
                f"{("" if not bonus["song"]
                    else " :cd:" if bonus["bonus_amount"] == 3
                    else " :birthday: :dvd:")}"
                f"{"~~" if bonus["bonus_end"] < current_date else ""}"
            ),
            value=(
                f"{"~~" if bonus["bonus_end"] < current_date else ""}"
                f"{bonus["bonus_amount"]}% | "
                f"{bonus["bonus_start"].strftime("%B %d").replace(" 0", " ")} "
                f"- {bonus["bonus_end"].strftime("%B %d").replace(" 0", " ")} | "
                f"{("Expired" if bonus["bonus_end"] < current_date
                    else f"Available <t:{int(bonus["bonus_start"].timestamp())}:R>"
                    if bonus["bonus_start"] > current_date
                    else f"Ends <t:{int((bonus["bonus_end"] + ONE_DAY).timestamp())}"
                    f":R>")}"
                f"{" :bangbang:" if bonus["bonus_start"] == last_date else ""}"
                f"{"~~" if bonus["bonus_end"] < current_date else ""}"
            ),
            inline=False,
        )
    embed.set_footer(text=f"Page {current_page}/{max_page}")
    return embed


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Bonus(bot))
