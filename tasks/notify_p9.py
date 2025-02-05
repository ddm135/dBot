from datetime import datetime, time, timedelta
from itertools import zip_longest
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from static.dConsts import BONUSES, sheetService


class NotifyP9(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.notify_p9.start()

    async def cog_unload(self):
        self.notify_p9.cancel()

    @tasks.loop(
        time=[
            time(
                hour=23,
                minute=0,
                second=0,
                microsecond=0,
                tzinfo=ZoneInfo("Asia/Seoul"),
            )
        ]
    )
    async def notify_p9(self):
        for game in BONUSES.values():
            current = datetime.now().replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
                tzinfo=ZoneInfo("Asia/Seoul"),
            )
            one_day = timedelta(days=1)
            current = current + one_day
            initial_msg = (
                f"# Bonus Reminder for {game['name']} on "
                f"<t:{int(current.timestamp())}:f>"
            )
            ping_result = (
                sheetService.values()
                .get(
                    spreadsheetId=game["pingId"],
                    range=game["pingRange"],
                )
                .execute()
            )
            pings = ping_result.get("values", [])
            pings_unpack = list(
                tuple(p for p in pair if p is not None) for pair in zip_longest(*pings)
            )
            if len(pings_unpack) != len(game["pingColumns"]):
                continue
            game_pinged_list = dict.fromkeys(
                pings_unpack[game["pingColumns"].index("users")], False
            )

            bonus_result = (
                sheetService.values()
                .get(
                    spreadsheetId=game["bonusId"],
                    range=game["bonusRange"],
                )
                .execute()
            )
            bonuses = bonus_result.get("values")
            artists = list(
                dict.fromkeys(
                    list(zip(*bonuses))[game["bonusColumns"].index("artist_name")]
                )
            )
            for artist in artists:
                artist_pings = next(
                    ping
                    for ping in pings
                    if ping[game["pingColumns"].index("artist_name")] == artist
                )
                if len(artist_pings) != len(game["pingColumns"]):
                    continue
                artist_ping_list = artist_pings[
                    game["pingColumns"].index("users")
                ].split(",")

                birthday_bonuses = []
                ne_birthday_bonuses = []
                album_bonuses = []
                notify_start = []
                notify_end = []
                last_birthday_start = None
                last_birthday_end = None
                next_birthday_start = None
                next_birthday_end = None
                for bonus in bonuses:
                    start = datetime.strptime(
                        bonus[game["bonusColumns"].index("bonus_start")].replace(
                            "\r", ""
                        ),
                        "%Y-%m-%d",
                    )
                    start = start.replace(tzinfo=ZoneInfo("Asia/Seoul"))
                    end = datetime.strptime(
                        bonus[game["bonusColumns"].index("bonus_end")].replace(
                            "\r", ""
                        ),
                        "%Y-%m-%d",
                    )
                    end = end.replace(tzinfo=ZoneInfo("Asia/Seoul"))
                    if (
                        start < current
                        and artist == bonus[game["bonusColumns"].index("artist_name")]
                        and bonus[game["bonusColumns"].index("member_name")]
                    ):
                        last_birthday_start = start

                    if (
                        end < current
                        and artist == bonus[game["bonusColumns"].index("artist_name")]
                        and bonus[game["bonusColumns"].index("member_name")]
                    ):
                        last_birthday_end = end

                    if (
                        current < start
                        and artist == bonus[game["bonusColumns"].index("artist_name")]
                        and bonus[game["bonusColumns"].index("member_name")]
                        and not next_birthday_start
                    ):
                        next_birthday_start = start

                    if (
                        current < end
                        and artist == bonus[game["bonusColumns"].index("artist_name")]
                        and bonus[game["bonusColumns"].index("member_name")]
                        and not next_birthday_end
                    ):
                        next_birthday_end = end

                    if (
                        start <= current <= end
                        and artist == bonus[game["bonusColumns"].index("artist_name")]
                    ):
                        if bonus[game["bonusColumns"].index("member_name")]:
                            birthday_bonuses.append(bonus)
                            if current + one_day <= end:
                                ne_birthday_bonuses.append(bonus)
                        else:
                            album_bonuses.append(bonus)

                rebum_bonuses = album_bonuses.copy()
                ne_birthday_total = 0
                if ne_birthday_bonuses:
                    ne_birthday_amounts = list(zip(*ne_birthday_bonuses))[
                        game["bonusColumns"].index("bonus_amount")
                    ]
                    for amt in ne_birthday_amounts:
                        ne_birthday_total += int(amt.replace("%", "").replace("\r", ""))

                birthday_total = 0
                if birthday_bonuses:
                    birthday_amounts = list(zip(*birthday_bonuses))[
                        game["bonusColumns"].index("bonus_amount")
                    ]
                    for amt in birthday_amounts:
                        birthday_total += int(amt.replace("%", "").replace("\r", ""))
                    birthday_members = " + ".join(
                        list(zip(*birthday_bonuses))[
                            game["bonusColumns"].index("member_name")
                        ]
                    ).replace("\r", "")

                    birthday_ends = []
                    for dt in list(zip(*birthday_bonuses))[
                        game["bonusColumns"].index("bonus_end")
                    ]:
                        be = datetime.strptime(dt.replace("\r", ""), "%Y-%m-%d")
                        be = be.replace(tzinfo=ZoneInfo("Asia/Seoul"))
                        birthday_ends.append(be)
                    birthday_bonus_end = min(
                        [
                            x
                            for x in (
                                *birthday_ends,
                                next_birthday_end,
                                next_birthday_start,
                            )
                            if x is not None
                        ]
                    )

                    birthday_starts = []
                    for dt in list(zip(*birthday_bonuses))[
                        game["bonusColumns"].index("bonus_start")
                    ]:
                        bs = datetime.strptime(dt.replace("\r", ""), "%Y-%m-%d")
                        bs = bs.replace(tzinfo=ZoneInfo("Asia/Seoul"))
                        birthday_starts.append(bs)
                    birthday_bonus_start = max(
                        [
                            x
                            for x in (
                                *birthday_starts,
                                last_birthday_end,
                                last_birthday_start,
                            )
                            if x is not None
                        ]
                    )

                    for bonus in birthday_bonuses:
                        start = datetime.strptime(
                            bonus[game["bonusColumns"].index("bonus_start")], "%Y-%m-%d"
                        )
                        start = start.replace(tzinfo=ZoneInfo("Asia/Seoul"))
                        if start == current:
                            msg = (
                                f"> {birthday_members} - All Songs\n> {birthday_total}"
                                f"% | {start.strftime('%B %d').replace(' 0', ' ')} - "
                                f"{birthday_bonus_end.strftime('%B %d').replace(' 0', ' ')}"
                                f" | Available <t:{int(current.timestamp())}:R>\n"
                            )
                            notify_start.append(msg)

                            for bonus in album_bonuses:
                                end = datetime.strptime(
                                    bonus[
                                        game["bonusColumns"].index("bonus_end")
                                    ].replace("\r", ""),
                                    "%Y-%m-%d",
                                )
                                end = end.replace(tzinfo=ZoneInfo("Asia/Seoul"))
                                song_bonus_end = min(
                                    [
                                        x
                                        for x in (
                                            end,
                                            next_birthday_end,
                                            next_birthday_start,
                                        )
                                        if x is not None
                                    ]
                                )

                                song_total = birthday_total + int(
                                    bonus[game["bonusColumns"].index("bonus_amount")]
                                    .replace("%", "")
                                    .replace("\r", "")
                                )
                                album_name = bonus[
                                    game["bonusColumns"].index("album_name")
                                ].replace("\r", "")
                                song_name = bonus[
                                    game["bonusColumns"].index("song_name")
                                ].replace("\r", "")
                                song_duration = bonus[
                                    game["bonusColumns"].index("duration")
                                ].replace("\r", "")

                                msg = (
                                    f"> {album_name} - {song_name} ({song_duration})\n"
                                    f"> {song_total}% | "
                                    f"{start.strftime('%B %d').replace(' 0', ' ')} - "
                                    f"{song_bonus_end.strftime('%B %d').replace(' 0', ' ')}"
                                    f" | Available <t:{int(current.timestamp())}:R>\n"
                                )
                                notify_start.append(msg)

                            album_bonuses = []
                            break

                    for bonus in birthday_bonuses:
                        end = datetime.strptime(
                            bonus[game["bonusColumns"].index("bonus_end")].replace(
                                "\r", ""
                            ),
                            "%Y-%m-%d",
                        )
                        end = end.replace(tzinfo=ZoneInfo("Asia/Seoul"))
                        if end == current + one_day:
                            msg = (
                                f"> {birthday_members} - All Songs\n> {birthday_total}% | "
                                f"{birthday_bonus_start.strftime('%B %d').replace(' 0', ' ')}"
                                f" - {end.strftime('%B %d').replace(' 0', ' ')}"
                                f" | Ends <t:{int(current.timestamp())}:R>\n"
                            )
                            notify_end.append(msg)

                            for bonus in rebum_bonuses:
                                start = datetime.strptime(
                                    bonus[game["bonusColumns"].index("bonus_start")],
                                    "%Y-%m-%d",
                                )
                                start = datetime.now(ZoneInfo("Asia/Seoul")).replace(
                                    year=start.year,
                                    month=start.month,
                                    day=start.day,
                                    hour=0,
                                    minute=0,
                                    second=0,
                                    microsecond=0,
                                )
                                song_bonus_start = max(
                                    [
                                        x
                                        for x in (
                                            start,
                                            last_birthday_end,
                                            last_birthday_start,
                                        )
                                        if x is not None
                                    ]
                                )

                                song_total = birthday_total + int(
                                    bonus[game["bonusColumns"].index("bonus_amount")]
                                    .replace("%", "")
                                    .replace("\r", "")
                                )
                                album_name = bonus[
                                    game["bonusColumns"].index("album_name")
                                ].replace("\r", "")
                                song_name = bonus[
                                    game["bonusColumns"].index("song_name")
                                ].replace("\r", "")
                                song_duration = bonus[
                                    game["bonusColumns"].index("duration")
                                ].replace("\r", "")

                                msg = (
                                    f"> {album_name} - {song_name} ({song_duration})\n"
                                    f"> {song_total}% | "
                                    f"{song_bonus_start.strftime('%B %d').replace(' 0', ' ')}"
                                    f" - {end.strftime('%B %d').replace(' 0', ' ')}"
                                    f" | Ends <t:{int(current.timestamp())}:R>\n"
                                )
                                notify_end.append(msg)

                            rebum_bonuses = []
                            break

                for bonus in album_bonuses:
                    start = datetime.strptime(
                        bonus[game["bonusColumns"].index("bonus_start")].replace(
                            "\r", ""
                        ),
                        "%Y-%m-%d",
                    )
                    start = start.replace(tzinfo=ZoneInfo("Asia/Seoul"))

                    if start == current:
                        end = datetime.strptime(
                            bonus[game["bonusColumns"].index("bonus_end")].replace(
                                "\r", ""
                            ),
                            "%Y-%m-%d",
                        )
                        end = end.replace(tzinfo=ZoneInfo("Asia/Seoul"))
                        song_bonus_start = max(
                            [
                                x
                                for x in (start, last_birthday_start, last_birthday_end)
                                if x is not None
                            ]
                        )
                        song_bonus_end = min(
                            [
                                x
                                for x in (end, next_birthday_end, next_birthday_start)
                                if x is not None
                            ]
                        )

                        song_total = birthday_total + int(
                            bonus[game["bonusColumns"].index("bonus_amount")]
                            .replace("%", "")
                            .replace("\r", "")
                        )
                        album_name = bonus[
                            game["bonusColumns"].index("album_name")
                        ].replace("\r", "")
                        song_name = bonus[
                            game["bonusColumns"].index("song_name")
                        ].replace("\r", "")
                        song_duration = bonus[
                            game["bonusColumns"].index("duration")
                        ].replace("\r", "")

                        msg = (
                            f"> {album_name} - {song_name} ({song_duration})\n"
                            f"> {song_total}% | "
                            f"{song_bonus_start.strftime('%B %d').replace(' 0', ' ')}"
                            f" - {song_bonus_end.strftime('%B %d').replace(' 0', ' ')}"
                            f" | Available <t:{int(current.timestamp())}:R>\n"
                        )
                        notify_start.append(msg)

                for bonus in rebum_bonuses:
                    end = datetime.strptime(
                        bonus[game["bonusColumns"].index("bonus_end")].replace(
                            "\r", ""
                        ),
                        "%Y-%m-%d",
                    )
                    end = end.replace(tzinfo=ZoneInfo("Asia/Seoul"))

                    if end == current + one_day:
                        start = datetime.strptime(
                            bonus[game["bonusColumns"].index("bonus_start")].replace(
                                "\r", ""
                            ),
                            "%Y-%m-%d",
                        )
                        start = start.replace(tzinfo=ZoneInfo("Asia/Seoul"))
                        song_bonus_start = max(
                            [
                                x
                                for x in (start, last_birthday_start, last_birthday_end)
                                if x is not None
                            ]
                        )
                        song_bonus_end = min(
                            [
                                x
                                for x in (end, next_birthday_end, next_birthday_start)
                                if x is not None
                            ]
                        )

                        song_total = ne_birthday_total + int(
                            bonus[game["bonusColumns"].index("bonus_amount")]
                            .replace("%", "")
                            .replace("\r", "")
                        )
                        album_name = bonus[
                            game["bonusColumns"].index("album_name")
                        ].replace("\r", "")
                        song_name = bonus[
                            game["bonusColumns"].index("song_name")
                        ].replace("\r", "")
                        song_duration = bonus[
                            game["bonusColumns"].index("duration")
                        ].replace("\r", "")

                        msg = (
                            f"> {album_name} - {song_name} ({song_duration})\n"
                            f"> {song_total}% | "
                            f"{song_bonus_start.strftime('%B %d').replace(' 0', ' ')}"
                            f" - {song_bonus_end.strftime('%B %d').replace(' 0', ' ')}"
                            f" | Ends <t:{int(current.timestamp())}:R>\n"
                        )
                        notify_end.append(msg)

                # print(artist)
                # print("Start: ", end="")
                # pprint(notify_start)
                # print("End: ", end="")
                # pprint(notify_end)
                if notify_start or notify_end:
                    for user_id in artist_ping_list:
                        user = await self.bot.fetch_user(int(user_id))
                        if not game_pinged_list[user_id]:
                            await user.send(f"{initial_msg}")
                            game_pinged_list[user_id] = True
                        embed = discord.Embed(
                            title=artist, color=discord.Color.random()
                        )
                        if notify_start:
                            embed.add_field(
                                name="Upcoming :green_circle:",
                                value="".join(notify_start),
                            )
                        if notify_end:
                            embed.add_field(
                                name="Expiring :orange_circle:",
                                value="".join(notify_end),
                            )
                        await user.send(embed=embed, silent=True)

    @notify_p9.before_loop
    async def before_notify_p9(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(NotifyP9(bot))
