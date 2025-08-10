from datetime import datetime, time
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

from statics.consts import (
    BONUS_OFFSET,
    GAMES,
    STATUS_CHANNEL,
    TIMEZONES,
)

from .embeds import NotifyBonusEmbed

if TYPE_CHECKING:
    from dBot import dBot


class NotifyBonus(commands.Cog):
    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.notify_bonus.start()

    async def cog_unload(self) -> None:
        self.notify_bonus.cancel()

    @tasks.loop(time=[time(hour=h) for h in range(24)])
    async def notify_bonus(self) -> None:
        cog = self.bot.get_cog("GoogleSheets")

        for game, game_details in GAMES.items():
            if not (bonus_details := game_details.get("bonus")) or not (
                ping_details := game_details.get("ping")
            ):
                continue

            timezone = game_details["timezone"]
            current_date = datetime.now(tz=timezone)
            if current_date.hour != 23:
                continue

            game_name = game_details["name"]
            current_date = (
                current_date.replace(
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
                + BONUS_OFFSET
            )
            initial_msg = (
                f"## Bonus Reminder for {game_name} on "
                f"<t:{int(current_date.timestamp())}:f>"
            )

            ping_columns = ping_details["columns"]
            ping_users_index = ping_columns.index("users")
            ping_artist_index = ping_columns.index("artist_name")

            ping_data = await cog.get_sheet_data(  # type: ignore[union-attr]
                ping_details["spreadsheetId"],
                ping_details["range"],
                "kr" if game_details["timezone"] == TIMEZONES["KST"] else None,
            )
            game_ping_dict = dict.fromkeys(
                (
                    user
                    for users in tuple(zip(*ping_data))[ping_users_index]
                    for user in users.split(",")
                ),
                False,
            )
            game_ping_dict.pop("", None)
            if not game_ping_dict:
                continue

            bonus_columns = bonus_details["columns"]
            member_name_index = bonus_columns.index("member_name")
            album_name_index = bonus_columns.index("album_name")
            song_name_index = bonus_columns.index("song_name")
            duration_index = bonus_columns.index("duration")
            bonus_start_index = bonus_columns.index("bonus_start")
            bonus_end_index = bonus_columns.index("bonus_end")
            bonus_amount_index = bonus_columns.index("bonus_amount")

            bonus_data = self.bot.bonus[game]
            artists = bonus_data.keys()
            for artist in artists:
                artist_pings = next(
                    (ping for ping in ping_data if ping[ping_artist_index] == artist),
                    None,
                )
                if not artist_pings:
                    continue
                artist_ping_list = artist_pings[ping_users_index].split(",")
                if "" in artist_ping_list:
                    artist_ping_list.remove("")
                if not artist_ping_list:
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

                    if start_date < current_date and bonus[member_name_index]:
                        last_birthday_start = start_date

                    if end_date < current_date and bonus[member_name_index]:
                        last_birthday_end = end_date + BONUS_OFFSET

                    if (
                        not next_birthday_start
                        and current_date < start_date
                        and bonus[member_name_index]
                    ):
                        next_birthday_start = start_date - BONUS_OFFSET

                    if (
                        not next_birthday_end
                        and current_date < end_date
                        and bonus[member_name_index]
                    ):
                        next_birthday_end = end_date

                    if start_date <= current_date <= end_date:
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

                start_check = last_birthday_end != current_date
                end_check = next_birthday_start != current_date

                if birthday_bonuses and birthday_start and birthday_end:
                    if birthday_end == current_date and end_check:
                        msg = (
                            f"> {birthday_members} - **All Songs**\n> {birthday_total}%"
                            f" | {birthday_start.strftime("%B %d").replace(" 0", " ")} "
                            f"- {birthday_end.strftime("%B %d").replace(" 0", " ")}\n"
                        )
                        notify_end.append(msg)
                    elif birthday_start == current_date and start_check:
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

                    if song_start == current_date or song_end == current_date:
                        song_total = birthday_total + bonus[bonus_amount_index]
                        album_name = (
                            bonus[album_name_index]
                            .replace(r"*", r"\*")
                            .replace(r"_", r"\_")
                        )
                        song_name = (
                            bonus[song_name_index]
                            .replace(r"*", r"\*")
                            .replace(r"_", r"\_")
                        )
                        song_duration = bonus[duration_index]

                        if song_end == current_date and end_check:
                            msg = (
                                f"> {album_name} - **{song_name}** ({song_duration})\n"
                                f"> {song_total}% | "
                                f"{song_start.strftime("%B %d").replace(" 0", " ")} "
                                f"- {song_end.strftime("%B %d").replace(" 0", " ")}\n"
                            )
                            notify_end.append(msg)
                        elif song_start == current_date and start_check:
                            msg = (
                                f"> {album_name} - **{song_name}** ({song_duration})\n"
                                f"> {song_total}% | "
                                f"{song_start.strftime("%B %d").replace(" 0", " ")} "
                                f"- {song_end.strftime("%B %d").replace(" 0", " ")}\n"
                            )
                            notify_start.append(msg)

                if notify_start or notify_end:
                    embed = NotifyBonusEmbed(
                        artist,
                        None,
                        current_date,
                        notify_start,
                        notify_end,
                        game_details["color"],
                    )

                    for user_id in artist_ping_list:
                        int_user_id = int(user_id)
                        try:
                            user = self.bot.get_user(
                                int_user_id
                            ) or await self.bot.fetch_user(int_user_id)
                        except discord.NotFound:
                            continue

                        try:
                            if not game_ping_dict[user_id]:
                                game_ping_dict[user_id] = True
                                await user.send(initial_msg)

                            await user.send(embed=embed, silent=True)
                        except discord.Forbidden:
                            channel = self.bot.get_channel(
                                STATUS_CHANNEL
                            ) or await self.bot.fetch_channel(STATUS_CHANNEL)
                            assert isinstance(channel, discord.TextChannel)
                            await channel.send(
                                f"<@{self.bot.owner_id}> Failed to send bonus ping to"
                                f" {user.name} ({user.id}) for {game_name} - {artist}."
                            )
                        except discord.HTTPException as e:
                            channel = self.bot.get_channel(
                                STATUS_CHANNEL
                            ) or await self.bot.fetch_channel(STATUS_CHANNEL)
                            assert isinstance(channel, discord.TextChannel)
                            await channel.send(
                                f"<@{self.bot.owner_id}> Failed to send bonus ping for"
                                f" {game_name} - {artist}. Check console for details."
                            )
                            print(e)
                            break

    @notify_bonus.before_loop
    async def before_notify_bonus(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: "dBot") -> None:
    await bot.add_cog(NotifyBonus(bot))
