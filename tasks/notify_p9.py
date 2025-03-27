from datetime import datetime, time
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

from statics.consts import GAMES, ONE_DAY, TIMEZONES
from statics.helpers import get_sheet_data

if TYPE_CHECKING:
    from dBot import dBot


class NotifyP9(commands.Cog):

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.notify_p9.start()
        await super().cog_load()

    async def cog_unload(self) -> None:
        self.notify_p9.cancel()
        await super().cog_unload()

    @tasks.loop(
        time=[
            time(
                hour=23,
                minute=0,
                second=0,
                microsecond=0,
                tzinfo=TIMEZONES["KST"],
            )
        ]
    )
    async def notify_p9(self) -> None:
        for game_details in GAMES.values():
            if (timezone := game_details["timezone"]) not in (
                TIMEZONES["KST"],
                TIMEZONES["JST"],
            ) or game_details["name"] == "SUPERSTAR JYP":
                continue
            print(game_details["name"])
            date_format = game_details["dateFormat"]
            ping_columns = game_details["pingColumns"]
            bonus_columns = game_details["bonusColumns"]

            current_date = (
                datetime.now().replace(
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                    tzinfo=timezone,
                )
                + ONE_DAY
            )
            initial_msg = (
                f"## Bonus Reminder for {game_details["name"]} on "
                f"<t:{int(current_date.timestamp())}:f>"
            )

            ping_data = get_sheet_data(
                game_details["pingId"], game_details["pingRange"]
            )
            game_ping_dict = dict.fromkeys(
                (
                    user
                    for users in tuple(zip(*ping_data))[ping_columns.index("users")]
                    for user in users.split(",")
                ),
                False,
            )
            game_ping_dict.pop("", None)
            if not game_ping_dict:
                continue

            artist_name_index = bonus_columns.index("artist_name")
            member_name_index = bonus_columns.index("member_name")
            bonus_start_index = bonus_columns.index("bonus_start")
            bonus_end_index = bonus_columns.index("bonus_end")
            bonus_amount_index = bonus_columns.index("bonus_amount")

            bonus_data = get_sheet_data(
                game_details["bonusId"],
                game_details["bonusRange"],
                "KR" if timezone == TIMEZONES["KST"] else None,
            )
            artists = tuple(dict.fromkeys(tuple(zip(*bonus_data))[artist_name_index]))
            for artist in artists:
                print(artist)
                artist_pings = next(
                    (
                        ping
                        for ping in ping_data
                        if ping[ping_columns.index("artist_name")] == artist
                    ),
                    None,
                )
                if not artist_pings:
                    continue
                artist_ping_list = artist_pings[ping_columns.index("users")].split(",")
                artist_ping_list.remove("") if "" in artist_ping_list else None
                if not artist_ping_list:
                    continue

                birthday_bonuses: list[list[str]] = []
                album_bonuses: list[list[str]] = []
                notify_start = []
                notify_end = []
                last_birthday_start = None
                last_birthday_end = None
                next_birthday_start = None
                next_birthday_end = None
                for bonus in bonus_data:
                    start_date = datetime.strptime(
                        bonus[bonus_start_index], date_format
                    ).replace(tzinfo=timezone)
                    end_date = datetime.strptime(
                        bonus[bonus_end_index], date_format
                    ).replace(tzinfo=timezone)

                    if (
                        start_date < current_date
                        and artist == bonus[artist_name_index]
                        and bonus[member_name_index]
                    ):
                        last_birthday_start = start_date

                    if (
                        end_date < current_date
                        and artist == bonus[artist_name_index]
                        and bonus[member_name_index]
                    ):
                        last_birthday_end = end_date + ONE_DAY

                    if (
                        not next_birthday_start
                        and current_date < start_date
                        and artist == bonus[artist_name_index]
                        and bonus[member_name_index]
                    ):
                        next_birthday_start = start_date - ONE_DAY

                    if (
                        not next_birthday_end
                        and current_date < end_date
                        and artist == bonus[artist_name_index]
                        and bonus[member_name_index]
                    ):
                        next_birthday_end = end_date

                    if (
                        start_date <= current_date <= end_date
                        and artist == bonus[artist_name_index]
                    ):
                        if bonus[member_name_index]:
                            birthday_bonuses.append(bonus)
                        else:
                            album_bonuses.append(bonus)

                print(birthday_bonuses)
                print(album_bonuses)

                birthday_members = ""
                birthday_total = 0
                birthday_starts = []
                birthday_ends = []
                if birthday_bonuses:
                    birthday_zip: tuple[tuple[str, ...], ...] = tuple(
                        zip(*birthday_bonuses)
                    )
                    birthday_members = " + ".join(birthday_zip[member_name_index])
                    birthday_amounts = birthday_zip[bonus_amount_index]
                    for amt in birthday_amounts:
                        birthday_total += int(amt.replace("%", ""))

                    for dt in birthday_zip[bonus_start_index]:
                        bs = datetime.strptime(dt, date_format).replace(tzinfo=timezone)
                        birthday_starts.append(bs)

                    for dt in birthday_zip[bonus_end_index]:
                        be = datetime.strptime(dt, date_format).replace(tzinfo=timezone)
                        birthday_ends.append(be)

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
                    start_date = datetime.strptime(
                        bonus[bonus_start_index], date_format
                    ).replace(tzinfo=timezone)
                    end_date = datetime.strptime(
                        bonus[bonus_end_index], date_format
                    ).replace(tzinfo=timezone)

                    song_start = max(
                        x for x in (start_date, birthday_start) if x is not None
                    )
                    song_end = min(x for x in (end_date, birthday_end) if x is not None)

                    if song_start == current_date or song_end == current_date:
                        song_total = birthday_total + int(
                            bonus[bonus_amount_index].replace("%", "")
                        )
                        album_name = bonus[bonus_columns.index("album_name")]
                        song_name = bonus[bonus_columns.index("song_name")]
                        song_duration = bonus[bonus_columns.index("duration")]

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
                    for user_id in artist_ping_list:
                        user = await self.bot.fetch_user(int(user_id))
                        if not game_ping_dict[user_id]:
                            await user.send(f"{initial_msg}")
                            game_ping_dict[user_id] = True
                        embed = discord.Embed(color=game_details["color"])
                        if notify_start:
                            embed.add_field(
                                name=(
                                    f"Available <t:{int(current_date.timestamp())}:R>"
                                    f" :green_circle:"
                                ),
                                value="".join(notify_start),
                                inline=False,
                            )
                        if notify_end:
                            embed.add_field(
                                name=(
                                    f"Ends "
                                    f"<t:{int((current_date + ONE_DAY).timestamp())}:R>"
                                    f" :orange_circle:"
                                ),
                                value="".join(notify_end),
                                inline=False,
                            )
                        embed.set_author(
                            name=artist,
                            icon_url=artist_pings[ping_columns.index("emblem")] or None,
                        )
                        # embed.set_footer(
                        #     text="Today's bonuses are sent early as the bot "
                        #     "won't be available 20:00 4/3 - 8:00 5/3 KST/JST"
                        # )
                        await user.send(embed=embed, silent=True)

    @notify_p9.before_loop
    async def before_notify_p9(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: "dBot") -> None:
    await bot.add_cog(NotifyP9(bot))
