from datetime import datetime, time, timedelta
from itertools import zip_longest
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from static.dConsts import GAMES, TIMEZONES
from static.dServices import sheetService


class NotifyP8(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.notify_p8.start()

    async def cog_unload(self):
        self.notify_p8.cancel()

    @tasks.loop(
        time=[
            time(
                hour=23,
                minute=0,
                second=0,
                microsecond=0,
                tzinfo=ZoneInfo("Asia/Manila"),
            )
        ]
    )
    async def notify_p8(self):
        for gameD in GAMES.values():
            if gameD["timezone"] not in (TIMEZONES["PHT"],):
                continue
            current = datetime.now().replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
                tzinfo=ZoneInfo("Asia/Manila"),
            )
            one_day = timedelta(days=1)
            current = current + one_day
            initial_msg = (
                f"# Bonus Reminder for {gameD["name"]} on "
                f"<t:{int(current.timestamp())}:f>"
            )
            ping_result = (
                sheetService
                .get(
                    spreadsheetId=gameD["pingId"],
                    range=gameD["pingRange"],
                )
                .execute()
            )
            pings = ping_result.get("values", [])
            pings_unpack = list(
                tuple(p for p in pair if p is not None) for pair in zip_longest(*pings)
            )
            if len(pings_unpack) != len(gameD["pingColumns"]):
                continue
            game_pinged_list = dict.fromkeys(
                pings_unpack[gameD["pingColumns"].index("users")], False
            )

            bonus_result = (
                sheetService.values()
                .get(
                    spreadsheetId=gameD["bonusId"],
                    range=gameD["bonusRange"],
                )
                .execute()
            )
            bonuses = bonus_result.get("values")
            artists = list(
                dict.fromkeys(
                    list(zip(*bonuses))[gameD["bonusColumns"].index("artist_name")]
                )
            )
            for artist in artists:
                artist_pings = next(
                    ping
                    for ping in pings
                    if ping[gameD["pingColumns"].index("artist_name")] == artist
                )
                if len(artist_pings) != len(gameD["pingColumns"]):
                    continue
                artist_ping_list = artist_pings[
                    gameD["pingColumns"].index("users")
                ].split(",")

                birthday_bonuses = []
                album_bonuses = []
                notify_start = []
                notify_end = []
                last_birthday_start = None
                last_birthday_end = None
                next_birthday_start = None
                next_birthday_end = None
                for bonus in bonuses:
                    start = datetime.strptime(
                        bonus[gameD["bonusColumns"].index("bonus_start")].replace(
                            "\r", ""
                        ),
                        "%Y-%m-%d",
                    )
                    start = start.replace(tzinfo=ZoneInfo("Asia/Manila"))
                    end = datetime.strptime(
                        bonus[gameD["bonusColumns"].index("bonus_end")].replace(
                            "\r", ""
                        ),
                        "%Y-%m-%d",
                    )
                    end = end.replace(tzinfo=ZoneInfo("Asia/Manila"))
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
                        current < start
                        and artist == bonus[gameD["bonusColumns"].index("artist_name")]
                        and bonus[gameD["bonusColumns"].index("member_name")]
                        and not next_birthday_start
                    ):
                        next_birthday_start = start - one_day

                    if (
                        current < end
                        and artist == bonus[gameD["bonusColumns"].index("artist_name")]
                        and bonus[gameD["bonusColumns"].index("member_name")]
                        and not next_birthday_end
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

                rebum_bonuses = album_bonuses.copy()

                birthday_total = 0
                if birthday_bonuses:
                    birthday_amounts = list(zip(*birthday_bonuses))[
                        gameD["bonusColumns"].index("bonus_amount")
                    ]
                    for amt in birthday_amounts:
                        birthday_total += int(amt.replace("%", "").replace("\r", ""))
                    birthday_members = " + ".join(
                        list(zip(*birthday_bonuses))[
                            gameD["bonusColumns"].index("member_name")
                        ]
                    ).replace("\r", "")

                    birthday_ends = []
                    for dt in list(zip(*birthday_bonuses))[
                        gameD["bonusColumns"].index("bonus_end")
                    ]:
                        be = datetime.strptime(dt.replace("\r", ""), "%Y-%m-%d")
                        be = be.replace(tzinfo=ZoneInfo("Asia/Manila"))
                        birthday_ends.append(be)
                    birthday_bonus_end = min(
                        x
                        for x in (
                            *birthday_ends,
                            next_birthday_end,
                            next_birthday_start,
                        )
                        if x is not None
                    )

                    birthday_starts = []
                    for dt in list(zip(*birthday_bonuses))[
                        gameD["bonusColumns"].index("bonus_start")
                    ]:
                        bs = datetime.strptime(dt.replace("\r", ""), "%Y-%m-%d")
                        bs = bs.replace(tzinfo=ZoneInfo("Asia/Manila"))
                        birthday_starts.append(bs)
                    birthday_bonus_start = max(
                        x
                        for x in (
                            *birthday_starts,
                            last_birthday_end,
                            last_birthday_start,
                        )
                        if x is not None
                    )

                    for bonus in birthday_bonuses:
                        start = datetime.strptime(
                            bonus[gameD["bonusColumns"].index("bonus_start")],
                            "%Y-%m-%d",
                        )
                        start = start.replace(tzinfo=ZoneInfo("Asia/Manila"))
                        if start == current:
                            msg = (
                                f"> {birthday_members} - All Songs\n> {birthday_total}"
                                f"% | {start.strftime("%B %d").replace(" 0", " ")} - "
                                f"{birthday_bonus_end.strftime("%B %d").replace(" 0", " ")}"
                                f" | Available <t:{int(current.timestamp())}:R>\n"
                            )
                            notify_start.append(msg)

                            for bonus in album_bonuses:
                                end = datetime.strptime(
                                    bonus[
                                        gameD["bonusColumns"].index("bonus_end")
                                    ].replace("\r", ""),
                                    "%Y-%m-%d",
                                )
                                end = end.replace(tzinfo=ZoneInfo("Asia/Manila"))
                                song_bonus_end = min(
                                    x
                                    for x in (
                                        end,
                                        next_birthday_end,
                                        next_birthday_start,
                                    )
                                    if x is not None
                                )

                                song_total = birthday_total + int(
                                    bonus[gameD["bonusColumns"].index("bonus_amount")]
                                    .replace("%", "")
                                    .replace("\r", "")
                                )
                                album_name = bonus[
                                    gameD["bonusColumns"].index("album_name")
                                ].replace("\r", "")
                                song_name = bonus[
                                    gameD["bonusColumns"].index("song_name")
                                ].replace("\r", "")
                                song_duration = bonus[
                                    gameD["bonusColumns"].index("duration")
                                ].replace("\r", "")

                                msg = (
                                    f"> {album_name} - {song_name} ({song_duration})\n"
                                    f"> {song_total}% | "
                                    f"{start.strftime("%B %d").replace(" 0", " ")} - "
                                    f"{song_bonus_end.strftime("%B %d").replace(" 0", " ")}"
                                    f" | Available <t:{int(current.timestamp())}:R>\n"
                                )
                                notify_start.append(msg)

                            album_bonuses = []
                            break

                    for bonus in birthday_bonuses:
                        end = datetime.strptime(
                            bonus[gameD["bonusColumns"].index("bonus_end")].replace(
                                "\r", ""
                            ),
                            "%Y-%m-%d",
                        )
                        end = end.replace(tzinfo=ZoneInfo("Asia/Manila"))
                        if end == current:
                            msg = (
                                f"> {birthday_members} - All Songs\n"
                                f"> {birthday_total}% | "
                                f"{birthday_bonus_start.strftime("%B %d").replace(" 0", " ")}"
                                f" - {end.strftime("%B %d").replace(" 0", " ")}"
                                f" | Ends <t:{int((current + one_day).timestamp())}:R>\n"
                            )
                            notify_end.append(msg)

                            for bonus in rebum_bonuses:
                                start = datetime.strptime(
                                    bonus[gameD["bonusColumns"].index("bonus_start")],
                                    "%Y-%m-%d",
                                )
                                start = datetime.now(ZoneInfo("Asia/Manila")).replace(
                                    year=start.year,
                                    month=start.month,
                                    day=start.day,
                                    hour=0,
                                    minute=0,
                                    second=0,
                                    microsecond=0,
                                )
                                song_bonus_start = max(
                                    x
                                    for x in (
                                        start,
                                        last_birthday_end,
                                        last_birthday_start,
                                    )
                                    if x is not None
                                )

                                song_total = birthday_total + int(
                                    bonus[gameD["bonusColumns"].index("bonus_amount")]
                                    .replace("%", "")
                                    .replace("\r", "")
                                )
                                album_name = bonus[
                                    gameD["bonusColumns"].index("album_name")
                                ].replace("\r", "")
                                song_name = bonus[
                                    gameD["bonusColumns"].index("song_name")
                                ].replace("\r", "")
                                song_duration = bonus[
                                    gameD["bonusColumns"].index("duration")
                                ].replace("\r", "")

                                msg = (
                                    f"> {album_name} - {song_name}"
                                    f" ({song_duration})\n> {song_total}% | "
                                    f"{song_bonus_start.strftime("%B %d").replace(" 0", " ")}"
                                    f" - {end.strftime("%B %d").replace(" 0", " ")}"
                                    f" | Ends <t:{int((current + one_day).timestamp())}:R>\n"
                                )
                                notify_end.append(msg)

                            rebum_bonuses = []
                            break

                for bonus in album_bonuses:
                    start = datetime.strptime(
                        bonus[gameD["bonusColumns"].index("bonus_start")].replace(
                            "\r", ""
                        ),
                        "%Y-%m-%d",
                    )
                    start = start.replace(tzinfo=ZoneInfo("Asia/Manila"))

                    if start == current:
                        end = datetime.strptime(
                            bonus[gameD["bonusColumns"].index("bonus_end")].replace(
                                "\r", ""
                            ),
                            "%Y-%m-%d",
                        )
                        end = end.replace(tzinfo=ZoneInfo("Asia/Manila"))
                        song_bonus_start = max(
                            x
                            for x in (start, last_birthday_start, last_birthday_end)
                            if x is not None
                        )
                        song_bonus_end = min(
                            x
                            for x in (end, next_birthday_end, next_birthday_start)
                            if x is not None
                        )

                        song_total = birthday_total + int(
                            bonus[gameD["bonusColumns"].index("bonus_amount")]
                            .replace("%", "")
                            .replace("\r", "")
                        )
                        album_name = bonus[
                            gameD["bonusColumns"].index("album_name")
                        ].replace("\r", "")
                        song_name = bonus[
                            gameD["bonusColumns"].index("song_name")
                        ].replace("\r", "")
                        song_duration = bonus[
                            gameD["bonusColumns"].index("duration")
                        ].replace("\r", "")

                        msg = (
                            f"> {album_name} - {song_name} ({song_duration})\n"
                            f"> {song_total}% | "
                            f"{song_bonus_start.strftime("%B %d").replace(" 0", " ")}"
                            f" - {song_bonus_end.strftime("%B %d").replace(" 0", " ")}"
                            f" | Available <t:{int(current.timestamp())}:R>\n"
                        )
                        notify_start.append(msg)

                for bonus in rebum_bonuses:
                    end = datetime.strptime(
                        bonus[gameD["bonusColumns"].index("bonus_end")].replace(
                            "\r", ""
                        ),
                        "%Y-%m-%d",
                    )
                    end = end.replace(tzinfo=ZoneInfo("Asia/Manila"))

                    if end == current:
                        start = datetime.strptime(
                            bonus[gameD["bonusColumns"].index("bonus_start")].replace(
                                "\r", ""
                            ),
                            "%Y-%m-%d",
                        )
                        start = start.replace(tzinfo=ZoneInfo("Asia/Manila"))
                        song_bonus_start = max(
                            x
                            for x in (start, last_birthday_start, last_birthday_end)
                            if x is not None
                        )
                        song_bonus_end = min(
                            x
                            for x in (end, next_birthday_end, next_birthday_start)
                            if x is not None
                        )

                        song_total = birthday_total + int(
                            bonus[gameD["bonusColumns"].index("bonus_amount")]
                            .replace("%", "")
                            .replace("\r", "")
                        )
                        album_name = bonus[
                            gameD["bonusColumns"].index("album_name")
                        ].replace("\r", "")
                        song_name = bonus[
                            gameD["bonusColumns"].index("song_name")
                        ].replace("\r", "")
                        song_duration = bonus[
                            gameD["bonusColumns"].index("duration")
                        ].replace("\r", "")

                        msg = (
                            f"> {album_name} - {song_name} ({song_duration})\n"
                            f"> {song_total}% | "
                            f"{song_bonus_start.strftime("%B %d").replace(" 0", " ")}"
                            f" - {song_bonus_end.strftime("%B %d").replace(" 0", " ")}"
                            f" | Ends <t:{int((current + one_day).timestamp())}:R>\n"
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
                                name="Upcoming :green_circle:",
                                value="".join(notify_start),
                                inline=False,
                            )
                        if notify_end:
                            embed.add_field(
                                name="Expiring :orange_circle:",
                                value="".join(notify_end),
                                inline=False,
                            )
                        embed.set_thumbnail(
                            url=artist_pings[gameD["pingColumns"].index("emblem")]
                        )
                        await user.send(embed=embed, silent=True)

    @notify_p8.before_loop
    async def before_notify_p8(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(NotifyP8(bot))
