from datetime import datetime, time
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

from statics.consts import BONUS_OFFSET, GAMES, STATUS_CHANNEL, TIMEZONES, Data

from .embeds import NotifyBonusEmbed

if TYPE_CHECKING:
    from dBot import dBot
    from tasks.data_sync import DataSync


class NotifyBonus(commands.Cog):
    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.notify_bonus.start()

    async def cog_unload(self) -> None:
        self.notify_bonus.cancel()

    @tasks.loop(time=[time(hour=h) for h in range(24)])
    async def notify_bonus(self) -> None:
        channel = self.bot.get_channel(STATUS_CHANNEL) or await self.bot.fetch_channel(
            STATUS_CHANNEL
        )
        assert isinstance(channel, discord.TextChannel)

        for game, game_details in GAMES.items():
            if not (bonus_details := game_details.get("bonus")):
                continue

            timezone = game_details["timezone"]
            current_date = datetime.now(tz=timezone)

            game_name = game_details["name"]
            notify_date = (
                current_date.replace(hour=0, minute=0, second=0, microsecond=0)
                + BONUS_OFFSET
            )
            initial_msg = (
                f"## Bonus Reminder for {game_name} on "
                f"<t:{int(notify_date.timestamp())}:f>"
            )
            to_send: dict[int, dict[str, bool]] = {}

            bonus_columns = bonus_details["columns"]
            song_id_index = bonus_columns.index("song_id")
            member_name_index = bonus_columns.index("member_name")
            album_name_index = bonus_columns.index("album_name")
            song_name_index = bonus_columns.index("song_name")
            bonus_start_index = bonus_columns.index("bonus_start")
            bonus_end_index = bonus_columns.index("bonus_end")
            bonus_amount_index = bonus_columns.index("bonus_amount")

            bonus_data = self.bot.bonus[game]
            for artist in bonus_data.keys():
                if not (artist_pings := self.bot.notify_bonus[game][artist]):
                    continue

                birthday_bonuses = []
                album_bonuses = []
                notify_start = []
                notify_end = []
                last_birthday_start = None
                last_birthday_end = None
                next_birthday_start = None
                next_birthday_end = None
                for bonus in bonus_data[artist]:
                    start_date = bonus[bonus_start_index]
                    end_date = bonus[bonus_end_index]

                    if start_date < notify_date and bonus[member_name_index]:
                        last_birthday_start = start_date

                    if end_date < notify_date and bonus[member_name_index]:
                        last_birthday_end = end_date + BONUS_OFFSET

                    if (
                        not next_birthday_start
                        and notify_date < start_date
                        and bonus[member_name_index]
                    ):
                        next_birthday_start = start_date - BONUS_OFFSET

                    if (
                        not next_birthday_end
                        and notify_date < end_date
                        and bonus[member_name_index]
                    ):
                        next_birthday_end = end_date

                    if start_date <= notify_date <= end_date:
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

                start_check = last_birthday_end != notify_date
                end_check = next_birthday_start != notify_date

                if birthday_bonuses and birthday_start and birthday_end:
                    if birthday_end == notify_date and end_check:
                        msg = (
                            f"> {birthday_members} - **All Songs**\n> {birthday_total}%"
                            f" | {birthday_start.strftime("%B %d").replace(" 0", " ")} "
                            f"- {birthday_end.strftime("%B %d").replace(" 0", " ")}\n"
                        )
                        notify_end.append(msg)
                    elif birthday_start == notify_date and start_check:
                        msg = (
                            f"> {birthday_members} - **All Songs**\n> {birthday_total}%"
                            f" | {birthday_start.strftime("%B %d").replace(" 0", " ")} "
                            f"- {birthday_end.strftime("%B %d").replace(" 0", " ")}\n"
                        )
                        notify_start.append(msg)

                for bonus in album_bonuses:
                    start_date = bonus[bonus_start_index]
                    end_date = bonus[bonus_end_index]

                    song_start = max(x for x in (start_date, birthday_start) if x)
                    song_end = min(x for x in (end_date, birthday_end) if x)

                    if song_start == notify_date or song_end == notify_date:
                        song_total = birthday_total + bonus[bonus_amount_index]
                        album_name = (
                            bonus[album_name_index]
                            .replace(r"*", r"\*")
                            .replace(r"_", r"\_")
                            .replace(r"`", r"\`")
                        )
                        song_name = (
                            bonus[song_name_index]
                            .replace(r"*", r"\*")
                            .replace(r"_", r"\_")
                            .replace(r"`", r"\`")
                        )
                        song_duration = self.bot.info_from_file[game][
                            bonus[song_id_index]
                        ]["sound"]["duration"]

                        if song_end == notify_date and end_check:
                            msg = (
                                f"> {album_name} - **{song_name}** ({song_duration})\n"
                                f"> {song_total}% | "
                                f"{song_start.strftime("%B %d").replace(" 0", " ")} "
                                f"- {song_end.strftime("%B %d").replace(" 0", " ")}\n"
                            )
                            notify_end.append(msg)
                        elif song_start == notify_date and start_check:
                            msg = (
                                f"> {album_name} - **{song_name}** ({song_duration})\n"
                                f"> {song_total}% | "
                                f"{song_start.strftime("%B %d").replace(" 0", " ")} "
                                f"- {song_end.strftime("%B %d").replace(" 0", " ")}\n"
                            )
                            notify_start.append(msg)

                if not notify_start and not notify_end:
                    continue

                icon = self.bot.artist[game][artist]["emblem"]
                for user_id in artist_pings:
                    try:
                        user = self.bot.get_user(user_id) or await self.bot.fetch_user(
                            user_id
                        )
                    except discord.NotFound:
                        continue

                    to_send.setdefault(
                        user_id,
                        {
                            "start": 24
                            - self.bot.notify_bonus[str(user_id)]["start"][0]
                            == current_date.hour,
                            "end": 24 - self.bot.notify_bonus[str(user_id)]["end"][0]
                            == current_date.hour,
                            "init": True,
                        },
                    )

                    if not (to_send[user_id]["start"] and notify_start) and not (
                        to_send[user_id]["end"] and notify_end
                    ):
                        continue

                    embed = NotifyBonusEmbed(
                        artist,
                        icon,
                        notify_date,
                        notify_start if to_send[user_id]["start"] else [],
                        notify_end if to_send[user_id]["end"] else [],
                        game_details["color"],
                    )

                    try:
                        if to_send[user_id]["init"]:
                            await user.send(initial_msg)
                            to_send[user_id]["init"] = False

                        await user.send(
                            embed=embed,
                            files=(
                                [discord.File(icon, filename="icon.png")]
                                if isinstance(icon, Path)
                                else []
                            ),
                            silent=True,
                        )
                    except discord.Forbidden:
                        await channel.send(
                            f"<@{self.bot.owner_id}> Failed to send bonus ping to"
                            f" {user.name} ({user.id}) for {game_name} - {artist}."
                        )
                    except discord.HTTPException as e:
                        await channel.send(
                            f"<@{self.bot.owner_id}> Failed to send bonus ping for"
                            f" {game_name} - {artist}. Check console for details."
                        )
                        print(e)
                        break

        if not datetime.now(tz=TIMEZONES["KST"]):
            for str_user_id in self.bot.notify_bonus:
                self.bot.notify_bonus[str_user_id]["start"] = self.bot.notify_bonus[
                    str_user_id
                ]["restart"]
                self.bot.notify_bonus[str_user_id]["end"] = self.bot.notify_bonus[
                    str_user_id
                ]["reend"]
            cog: "DataSync" = self.bot.get_cog("DataSync")  # type: ignore[assignment]
            cog.save_data(Data.NOTIFY_BONUS)

    @notify_bonus.before_loop
    async def before_notify_bonus(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: "dBot") -> None:
    await bot.add_cog(NotifyBonus(bot))
