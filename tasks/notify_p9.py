from datetime import datetime, time, timedelta

import discord
from discord.ext import commands, tasks

from static.dConsts import GAMES, TIMEZONES
from static.dHelpers import get_sheet_data


class NotifyP9(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
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
        one_day = timedelta(days=1)
        for gameD in GAMES.values():
            if (timezone := gameD["timezone"]) not in (
                TIMEZONES["KST"],
                TIMEZONES["JST"],
            ):
                continue
            current = (
                datetime.now().replace(
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                    tzinfo=timezone,
                )
                + one_day
            )
            initial_msg = (
                f"# Bonus Reminder for {gameD["name"]} on "
                f"<t:{int(current.timestamp())}:f>"
            )
            pings = get_sheet_data(gameD["pingId"], gameD["pingRange"])
            game_pinged_list = dict.fromkeys(
                (
                    user
                    for users in tuple(zip(*pings))[gameD["pingColumns"].index("users")]
                    for user in users.split(",")
                ),
                False,
            )
            game_pinged_list.pop("", None)
            if not game_pinged_list:
                continue

            bonuses = get_sheet_data(
                gameD["bonusId"],
                gameD["bonusRange"],
                "KR" if timezone == TIMEZONES["KST"] else None,
            )
            artists = tuple(
                dict.fromkeys(
                    tuple(zip(*bonuses))[gameD["bonusColumns"].index("artist_name")]
                )
            )
            for artist in artists:
                artist_pings = next(
                    ping
                    for ping in pings
                    if ping[gameD["pingColumns"].index("artist_name")] == artist
                )
                artist_ping_list = artist_pings[
                    gameD["pingColumns"].index("users")
                ].split(",")
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
                for bonus in bonuses:
                    start = datetime.strptime(
                        bonus[gameD["bonusColumns"].index("bonus_start")],
                        "%Y-%m-%d",
                    )
                    start = start.replace(tzinfo=timezone)
                    end = datetime.strptime(
                        bonus[gameD["bonusColumns"].index("bonus_end")],
                        "%Y-%m-%d",
                    )
                    end = end.replace(tzinfo=timezone)
                    if (
                        start < current
                        and artist == bonus[gameD["bonusColumns"].index("artist_name")]
                        and bonus[gameD["bonusColumns"].index("member_name")]
                    ):
                        last_birthday_start = start

                    if (
                        end < current
                        and artist == bonus[gameD["bonusColumns"].index("artist_name")]
                        and bonus[gameD["bonusColumns"].index("member_name")]
                    ):
                        last_birthday_end = end + one_day

                    if (
                        not next_birthday_start
                        and current < start
                        and artist == bonus[gameD["bonusColumns"].index("artist_name")]
                        and bonus[gameD["bonusColumns"].index("member_name")]
                    ):
                        next_birthday_start = start - one_day

                    if (
                        not next_birthday_end
                        and current < end
                        and artist == bonus[gameD["bonusColumns"].index("artist_name")]
                        and bonus[gameD["bonusColumns"].index("member_name")]
                    ):
                        next_birthday_end = end

                    if (
                        start <= current <= end
                        and artist == bonus[gameD["bonusColumns"].index("artist_name")]
                    ):
                        if bonus[gameD["bonusColumns"].index("member_name")]:
                            birthday_bonuses.append(bonus)
                        else:
                            album_bonuses.append(bonus)

                birthday_members = ""
                birthday_total = 0
                birthday_starts = []
                birthday_ends = []
                if birthday_bonuses:
                    birthday_zip: tuple[tuple[str, ...], ...] = tuple(
                        zip(*birthday_bonuses)
                    )
                    birthday_members = " + ".join(
                        birthday_zip[gameD["bonusColumns"].index("member_name")]
                    )
                    birthday_amounts = birthday_zip[
                        gameD["bonusColumns"].index("bonus_amount")
                    ]
                    for amt in birthday_amounts:
                        birthday_total += int(amt.replace("%", ""))

                    for dt in birthday_zip[gameD["bonusColumns"].index("bonus_start")]:
                        bs = datetime.strptime(dt, "%Y-%m-%d")
                        bs = bs.replace(tzinfo=timezone)
                        birthday_starts.append(bs)

                    for dt in birthday_zip[gameD["bonusColumns"].index("bonus_end")]:
                        be = datetime.strptime(dt, "%Y-%m-%d")
                        be = be.replace(tzinfo=timezone)
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

                if birthday_start and birthday_end and birthday_bonuses:
                    if birthday_start == current:
                        msg = (
                            f"> {birthday_members} - All Songs\n> {birthday_total}% "
                            f"| {birthday_start.strftime("%B %d").replace(" 0", " ")}"
                            f" - {birthday_end.strftime("%B %d").replace(" 0", " ")}\n"
                        )
                        notify_start.append(msg)

                    if birthday_end == current:
                        msg = (
                            f"> {birthday_members} - All Songs\n"
                            f"> {birthday_total}% | "
                            f"{birthday_start.strftime("%B %d").replace(" 0", " ")}"
                            f" - {birthday_end.strftime("%B %d").replace(" 0", " ")}\n"
                        )
                        notify_end.append(msg)

                for bonus in album_bonuses:
                    start = datetime.strptime(
                        bonus[gameD["bonusColumns"].index("bonus_start")],
                        "%Y-%m-%d",
                    )
                    start = start.replace(tzinfo=timezone)
                    song_start = max(
                        x for x in (start, birthday_start) if x is not None
                    )

                    end = datetime.strptime(
                        bonus[gameD["bonusColumns"].index("bonus_end")],
                        "%Y-%m-%d",
                    )
                    end = end.replace(tzinfo=timezone)
                    song_end = min(x for x in (end, birthday_end) if x is not None)

                    if song_start == current or song_end == current:
                        song_total = birthday_total + int(
                            bonus[gameD["bonusColumns"].index("bonus_amount")].replace(
                                "%", ""
                            )
                        )
                        album_name = bonus[gameD["bonusColumns"].index("album_name")]
                        song_name = bonus[gameD["bonusColumns"].index("song_name")]
                        song_duration = bonus[gameD["bonusColumns"].index("duration")]

                        if song_start == current:
                            msg = (
                                f"> {album_name} - {song_name} ({song_duration})\n"
                                f"> {song_total}% | "
                                f"{song_start.strftime("%B %d").replace(" 0", " ")}"
                                f" - {song_end.strftime("%B %d").replace(" 0", " ")}\n"
                            )
                            notify_start.append(msg)
                        elif song_end == current:
                            msg = (
                                f"> {album_name} - {song_name} ({song_duration})\n"
                                f"> {song_total}% | "
                                f"{song_start.strftime("%B %d").replace(" 0", " ")}"
                                f" - {song_end.strftime("%B %d").replace(" 0", " ")}\n"
                            )
                            notify_end.append(msg)

                if notify_start or notify_end:
                    for user_id in artist_ping_list:
                        user = await self.bot.fetch_user(int(user_id))
                        if not game_pinged_list[user_id]:
                            await user.send(f"{initial_msg}")
                            game_pinged_list[user_id] = True
                        embed = discord.Embed(title=artist, color=gameD["color"])
                        if notify_start:
                            embed.add_field(
                                name=(
                                    f"Available <t:{int(current.timestamp())}:R> "
                                    f":green_circle:"
                                ),
                                value="".join(notify_start),
                                inline=False,
                            )
                        if notify_end:
                            embed.add_field(
                                name=(
                                    f"Ends "
                                    f"<t:{int((current + one_day).timestamp())}:R> "
                                    f":orange_circle:"
                                ),
                                value="".join(notify_end),
                                inline=False,
                            )
                        embed.set_thumbnail(
                            url=artist_pings[gameD["pingColumns"].index("emblem")]
                        )
                        await user.send(embed=embed, silent=True)
        # for gameD in GAMES.values():
        #     if gameD["timezone"] not in (TIMEZONES["KST"], TIMEZONES["JST"]):
        #         continue
        #     current = datetime.now().replace(
        #         hour=0,
        #         minute=0,
        #         second=0,
        #         microsecond=0,
        #         tzinfo=ZoneInfo("Asia/Seoul"),
        #     )
        #     one_day = timedelta(days=1)
        #     current = current + one_day
        #     initial_msg = (
        #         f"# Bonus Reminder for {gameD["name"]} on "
        #         f"<t:{int(current.timestamp())}:f>"
        #     )
        #     ping_result = sheetService.get(
        #         spreadsheetId=gameD["pingId"],
        #         range=gameD["pingRange"],
        #     ).execute()
        #     pings = ping_result.get("values", [])
        #     pings_unpack = list(
        #         tuple(p for p in pair if p is not None) for pair in zip_longest(*pings)
        #     )
        #     game_pinged_list = dict.fromkeys(
        #         pings_unpack[gameD["pingColumns"].index("users")], False
        #     )

        #     bonus_result = sheetService.get(
        #         spreadsheetId=gameD["bonusId"],
        #         range=gameD["bonusRange"],
        #     ).execute()
        #     bonuses = bonus_result.get("values")
        #     artists = list(
        #         dict.fromkeys(
        #             list(zip(*bonuses))[gameD["bonusColumns"].index("artist_name")]
        #         )
        #     )
        #     for artist in artists:
        #         artist_pings = next(
        #             ping
        #             for ping in pings
        #             if ping[gameD["pingColumns"].index("artist_name")] == artist
        #         )
        #         artist_ping_list = artist_pings[
        #             gameD["pingColumns"].index("users")
        #         ].split(",")

        #         birthday_bonuses = []
        #         album_bonuses = []
        #         notify_start = []
        #         notify_end = []
        #         last_birthday_start = None
        #         last_birthday_end = None
        #         next_birthday_start = None
        #         next_birthday_end = None
        #         for bonus in bonuses:
        #             start = datetime.strptime(
        #                 bonus[gameD["bonusColumns"].index("bonus_start")].replace(
        #                     "\r", ""
        #                 ),
        #                 "%Y-%m-%d",
        #             )
        #             start = start.replace(tzinfo=ZoneInfo("Asia/Seoul"))
        #             end = datetime.strptime(
        #                 bonus[gameD["bonusColumns"].index("bonus_end")].replace(
        #                     "\r", ""
        #                 ),
        #                 "%Y-%m-%d",
        #             )
        #             end = end.replace(tzinfo=ZoneInfo("Asia/Seoul"))
        #             if (
        #                 start < current
        #                 and artist == bonus[gameD["bonusColumns"].index("artist_name")]
        #                 and bonus[gameD["bonusColumns"].index("member_name")]
        #             ):
        #                 last_birthday_start = start

        #             if (
        #                 end < current
        #                 and artist == bonus[gameD["bonusColumns"].index("artist_name")]
        #                 and bonus[gameD["bonusColumns"].index("member_name")]
        #             ):
        #                 last_birthday_end = end + one_day

        #             if (
        #                 current < start
        #                 and artist == bonus[gameD["bonusColumns"].index("artist_name")]
        #                 and bonus[gameD["bonusColumns"].index("member_name")]
        #                 and not next_birthday_start
        #             ):
        #                 next_birthday_start = start - one_day

        #             if (
        #                 current < end
        #                 and artist == bonus[gameD["bonusColumns"].index("artist_name")]
        #                 and bonus[gameD["bonusColumns"].index("member_name")]
        #                 and not next_birthday_end
        #             ):
        #                 next_birthday_end = end

        #             if (
        #                 start <= current <= end
        #                 and artist == bonus[gameD["bonusColumns"].index("artist_name")]
        #             ):
        #                 if bonus[gameD["bonusColumns"].index("member_name")]:
        #                     birthday_bonuses.append(bonus)
        #                 else:
        #                     album_bonuses.append(bonus)

        #         rebum_bonuses = album_bonuses.copy()

        #         birthday_total = 0
        #         if birthday_bonuses:
        #             birthday_amounts = list(zip(*birthday_bonuses))[
        #                 gameD["bonusColumns"].index("bonus_amount")
        #             ]
        #             for amt in birthday_amounts:
        #                 birthday_total += int(amt.replace("%", ""))
        #             birthday_members = " + ".join(
        #                 list(zip(*birthday_bonuses))[
        #                     gameD["bonusColumns"].index("member_name")
        #                 ]
        #             )

        #             birthday_ends = []
        #             for dt in list(zip(*birthday_bonuses))[
        #                 gameD["bonusColumns"].index("bonus_end")
        #             ]:
        #                 be = datetime.strptime(dt, "%Y-%m-%d")
        #                 be = be.replace(tzinfo=ZoneInfo("Asia/Seoul"))
        #                 birthday_ends.append(be)
        #             birthday_bonus_end = min(
        #                 x
        #                 for x in (
        #                     *birthday_ends,
        #                     next_birthday_end,
        #                     next_birthday_start,
        #                 )
        #                 if x is not None
        #             )

        #             birthday_starts = []
        #             for dt in list(zip(*birthday_bonuses))[
        #                 gameD["bonusColumns"].index("bonus_start")
        #             ]:
        #                 bs = datetime.strptime(dt, "%Y-%m-%d")
        #                 bs = bs.replace(tzinfo=ZoneInfo("Asia/Seoul"))
        #                 birthday_starts.append(bs)
        #             birthday_bonus_start = max(
        #                 x
        #                 for x in (
        #                     *birthday_starts,
        #                     last_birthday_end,
        #                     last_birthday_start,
        #                 )
        #                 if x is not None
        #             )

        #             for bonus in birthday_bonuses:
        #                 start = datetime.strptime(
        #                     bonus[gameD["bonusColumns"].index("bonus_start")],
        #                     "%Y-%m-%d",
        #                 )
        #                 start = start.replace(tzinfo=ZoneInfo("Asia/Seoul"))
        #                 if start == current:
        #                     msg = (
        #                         f"> {birthday_members} - All Songs\n> {birthday_total}"
        #                         f"% | {start.strftime("%B %d").replace(" 0", " ")} - "
        #                         f"{birthday_bonus_end.strftime("%B %d").replace(" 0", " ")}\n"
        #                     )
        #                     notify_start.append(msg)

        #                     for bonus in album_bonuses:
        #                         end = datetime.strptime(
        #                             bonus[gameD["bonusColumns"].index("bonus_end")],
        #                             "%Y-%m-%d",
        #                         )
        #                         end = end.replace(tzinfo=ZoneInfo("Asia/Seoul"))
        #                         song_bonus_end = min(
        #                             x
        #                             for x in (
        #                                 end,
        #                                 next_birthday_end,
        #                                 next_birthday_start,
        #                             )
        #                             if x is not None
        #                         )

        #                         song_total = birthday_total + int(
        #                             bonus[
        #                                 gameD["bonusColumns"].index("bonus_amount")
        #                             ].replace("%", "")
        #                         )
        #                         album_name = bonus[
        #                             gameD["bonusColumns"].index("album_name")
        #                         ]
        #                         song_name = bonus[
        #                             gameD["bonusColumns"].index("song_name")
        #                         ]
        #                         song_duration = bonus[
        #                             gameD["bonusColumns"].index("duration")
        #                         ]

        #                         msg = (
        #                             f"> {album_name} - {song_name} ({song_duration})\n"
        #                             f"> {song_total}% | "
        #                             f"{start.strftime("%B %d").replace(" 0", " ")} - "
        #                             f"{song_bonus_end.strftime("%B %d").replace(" 0", " ")}\n"
        #                         )
        #                         notify_start.append(msg)

        #                     album_bonuses = []
        #                     break

        #             for bonus in birthday_bonuses:
        #                 end = datetime.strptime(
        #                     bonus[gameD["bonusColumns"].index("bonus_end")].replace(
        #                         "\r", ""
        #                     ),
        #                     "%Y-%m-%d",
        #                 )
        #                 end = end.replace(tzinfo=ZoneInfo("Asia/Seoul"))
        #                 if end == current:
        #                     msg = (
        #                         f"> {birthday_members} - All Songs\n"
        #                         f"> {birthday_total}% | "
        #                         f"{birthday_bonus_start.strftime("%B %d").replace(" 0", " ")}"
        #                         f" - {end.strftime("%B %d").replace(" 0", " ")}\n"
        #                     )
        #                     notify_end.append(msg)

        #                     for bonus in rebum_bonuses:
        #                         start = datetime.strptime(
        #                             bonus[gameD["bonusColumns"].index("bonus_start")],
        #                             "%Y-%m-%d",
        #                         )
        #                         start = datetime.now(ZoneInfo("Asia/Seoul")).replace(
        #                             year=start.year,
        #                             month=start.month,
        #                             day=start.day,
        #                             hour=0,
        #                             minute=0,
        #                             second=0,
        #                             microsecond=0,
        #                         )
        #                         song_bonus_start = max(
        #                             x
        #                             for x in (
        #                                 start,
        #                                 last_birthday_end,
        #                                 last_birthday_start,
        #                             )
        #                             if x is not None
        #                         )

        #                         song_total = birthday_total + int(
        #                             bonus[
        #                                 gameD["bonusColumns"].index("bonus_amount")
        #                             ].replace("%", "")
        #                         )
        #                         album_name = bonus[
        #                             gameD["bonusColumns"].index("album_name")
        #                         ]
        #                         song_name = bonus[
        #                             gameD["bonusColumns"].index("song_name")
        #                         ]
        #                         song_duration = bonus[
        #                             gameD["bonusColumns"].index("duration")
        #                         ]

        #                         msg = (
        #                             f"> {album_name} - {song_name}"
        #                             f" ({song_duration})\n> {song_total}% | "
        #                             f"{song_bonus_start.strftime("%B %d").replace(" 0", " ")}"
        #                             f" - {end.strftime("%B %d").replace(" 0", " ")}\n"
        #                         )
        #                         notify_end.append(msg)

        #                     rebum_bonuses = []
        #                     break

        #         for bonus in album_bonuses:
        #             start = datetime.strptime(
        #                 bonus[gameD["bonusColumns"].index("bonus_start")].replace(
        #                     "\r", ""
        #                 ),
        #                 "%Y-%m-%d",
        #             )
        #             start = start.replace(tzinfo=ZoneInfo("Asia/Seoul"))

        #             if start == current:
        #                 end = datetime.strptime(
        #                     bonus[gameD["bonusColumns"].index("bonus_end")].replace(
        #                         "\r", ""
        #                     ),
        #                     "%Y-%m-%d",
        #                 )
        #                 end = end.replace(tzinfo=ZoneInfo("Asia/Seoul"))
        #                 song_bonus_start = max(
        #                     x
        #                     for x in (start, last_birthday_start, last_birthday_end)
        #                     if x is not None
        #                 )
        #                 song_bonus_end = min(
        #                     x
        #                     for x in (end, next_birthday_end, next_birthday_start)
        #                     if x is not None
        #                 )

        #                 song_total = birthday_total + int(
        #                     bonus[gameD["bonusColumns"].index("bonus_amount")].replace(
        #                         "%", ""
        #                     )
        #                 )
        #                 album_name = bonus[gameD["bonusColumns"].index("album_name")]
        #                 song_name = bonus[gameD["bonusColumns"].index("song_name")]
        #                 song_duration = bonus[gameD["bonusColumns"].index("duration")]

        #                 msg = (
        #                     f"> {album_name} - {song_name} ({song_duration})\n"
        #                     f"> {song_total}% | "
        #                     f"{song_bonus_start.strftime("%B %d").replace(" 0", " ")} -"
        #                     f" {song_bonus_end.strftime("%B %d").replace(" 0", " ")}\n"
        #                 )
        #                 notify_start.append(msg)

        #         for bonus in rebum_bonuses:
        #             end = datetime.strptime(
        #                 bonus[gameD["bonusColumns"].index("bonus_end")].replace(
        #                     "\r", ""
        #                 ),
        #                 "%Y-%m-%d",
        #             )
        #             end = end.replace(tzinfo=ZoneInfo("Asia/Seoul"))

        #             if end == current:
        #                 start = datetime.strptime(
        #                     bonus[gameD["bonusColumns"].index("bonus_start")].replace(
        #                         "\r", ""
        #                     ),
        #                     "%Y-%m-%d",
        #                 )
        #                 start = start.replace(tzinfo=ZoneInfo("Asia/Seoul"))
        #                 song_bonus_start = max(
        #                     x
        #                     for x in (start, last_birthday_start, last_birthday_end)
        #                     if x is not None
        #                 )
        #                 song_bonus_end = min(
        #                     x
        #                     for x in (end, next_birthday_end, next_birthday_start)
        #                     if x is not None
        #                 )

        #                 song_total = birthday_total + int(
        #                     bonus[gameD["bonusColumns"].index("bonus_amount")].replace(
        #                         "%", ""
        #                     )
        #                 )
        #                 album_name = bonus[gameD["bonusColumns"].index("album_name")]
        #                 song_name = bonus[gameD["bonusColumns"].index("song_name")]
        #                 song_duration = bonus[gameD["bonusColumns"].index("duration")]

        #                 msg = (
        #                     f"> {album_name} - {song_name} ({song_duration})\n"
        #                     f"> {song_total}% | "
        #                     f"{song_bonus_start.strftime("%B %d").replace(" 0", " ")} -"
        #                     f" {song_bonus_end.strftime("%B %d").replace(" 0", " ")}\n"
        #                 )
        #                 notify_end.append(msg)

        #         if notify_start or notify_end:
        #             for user_id in artist_ping_list:
        #                 user = await self.bot.fetch_user(int(user_id))
        #                 if not game_pinged_list[user_id]:
        #                     await user.send(f"{initial_msg}")
        #                     game_pinged_list[user_id] = True
        #                 embed = discord.Embed(title=artist, color=gameD["color"])
        #                 if notify_start:
        #                     embed.add_field(
        #                         name=(
        #                             f"Available <t:{int(current.timestamp())}:R> "
        #                             f":green_circle:"
        #                         ),
        #                         value="".join(notify_start),
        #                         inline=False,
        #                     )
        #                 if notify_end:
        #                     embed.add_field(
        #                         name=(
        #                             f"Ends "
        #                             f"<t:{int((current + one_day).timestamp())}:R> "
        #                             f":orange_circle:"
        #                         ),
        #                         value="".join(notify_end),
        #                         inline=False,
        #                     )
        #                 embed.set_thumbnail(
        #                     url=artist_pings[gameD["pingColumns"].index("emblem")]
        #                 )
        #                 await user.send(embed=embed, silent=True)

    @notify_p9.before_loop
    async def before_notify_p9(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(NotifyP9(bot))
