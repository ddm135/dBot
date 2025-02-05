from datetime import datetime, timedelta
from pprint import pprint
from time import sleep
from zoneinfo import ZoneInfo

from static.dConsts import sheetService

result = (
    sheetService.values()
    .get(
        spreadsheetId="1Ng57BGCDj025bxwCBbQulYFhRjS5runy5HnbStY_xSw",
        range="Bonuses!A2:O",
    )
    .execute()
)
bonuses = result.get("values")
artists = list(dict.fromkeys(list(zip(*bonuses))[2]))
current = datetime(
    year=2024,
    month=12,
    day=31,
    hour=0,
    minute=0,
    second=0,
    microsecond=0,
    tzinfo=ZoneInfo("Asia/Tokyo"),
)
while True:
    current = current + timedelta(days=1)
    if current == datetime(
        year=2025,
        month=12,
        day=31,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
        tzinfo=ZoneInfo("Asia/Tokyo"),
    ):
        break
    print(current)
    for artist in artists:
        birthday_bonuses = []
        album_bonuses = []
        notify_start = []
        notify_end = []
        last_birthday_start = None
        last_birthday_end = None
        next_birthday_start = None
        next_birthday_end = None
        for bonus in bonuses:
            start = datetime.strptime(bonus[8].replace("\r", ""), "%Y-%m-%d")
            start = start.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
            end = datetime.strptime(bonus[9].replace("\r", ""), "%Y-%m-%d")
            end = end.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
            if start < current and artist == bonus[2] and bonus[3]:
                last_birthday_start = start

            if end < current and artist == bonus[2] and bonus[3]:
                last_birthday_end = end

            if (
                current < start
                and artist == bonus[2]
                and bonus[3]
                and not next_birthday_start
            ):
                next_birthday_start = start

            if (
                current < end
                and artist == bonus[2]
                and bonus[3]
                and not next_birthday_end
            ):
                next_birthday_end = end

            if start <= current <= end and artist == bonus[2]:
                if bonus[3]:
                    birthday_bonuses.append(bonus)
                else:
                    album_bonuses.append(bonus)

        rebum_bonuses = album_bonuses.copy()
        birthday_total = 0
        if birthday_bonuses:
            birthday_amounts = list(zip(*birthday_bonuses))[1]
            for amt in birthday_amounts:
                birthday_total += int(amt.replace("%", "").replace("\r", ""))
            birthday_members = " + ".join(list(zip(*birthday_bonuses))[3]).replace(
                "\r", ""
            )

            birthday_ends = []
            for dt in list(zip(*birthday_bonuses))[9]:
                be = datetime.strptime(dt.replace("\r", ""), "%Y-%m-%d")
                be = be.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
                birthday_ends.append(be)
            birthday_bonus_end = min(
                [
                    x
                    for x in (*birthday_ends, next_birthday_end, next_birthday_start)
                    if x is not None
                ]
            )

            birthday_starts = []
            for dt in list(zip(*birthday_bonuses))[8]:
                bs = datetime.strptime(dt.replace("\r", ""), "%Y-%m-%d")
                bs = bs.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
                birthday_starts.append(bs)
            birthday_bonus_start = max(
                [
                    x
                    for x in (*birthday_starts, last_birthday_end, last_birthday_start)
                    if x is not None
                ]
            )

            for bonus in birthday_bonuses:
                start = datetime.strptime(bonus[8], "%Y-%m-%d")
                start = start.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
                if start == current:
                    msg = (
                        f"{birthday_members}\n{birthday_total}% | "
                        f"{start.strftime('%B %d').replace(' 0', ' ')} - "
                        f"{birthday_bonus_end.strftime('%B %d').replace(' 0', ' ')}"
                        f" | Available <t:{int(current.timestamp())}:R>\n"
                    )
                    notify_start.append(msg)

                    for bonus in album_bonuses:
                        end = datetime.strptime(bonus[9].replace("\r", ""), "%Y-%m-%d")
                        end = end.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
                        song_bonus_end = min(
                            [
                                x
                                for x in (end, next_birthday_end, next_birthday_start)
                                if x is not None
                            ]
                        )

                        song_total = birthday_total + int(
                            bonus[1].replace("%", "").replace("\r", "")
                        )
                        album_name = bonus[4].replace("\r", "")
                        song_name = bonus[5].replace("\r", "")
                        song_duration = bonus[6].replace("\r", "")

                        msg = (
                            f"{album_name} - {song_name} ({song_duration})\n"
                            f"{song_total}% | "
                            f"{start.strftime('%B %d').replace(' 0', ' ')} - "
                            f"{song_bonus_end.strftime('%B %d').replace(' 0', ' ')}"
                            f" | Available <t:{int(current.timestamp())}:R>\n"
                        )
                        notify_start.append(msg)

                    album_bonuses = []
                    break

            for bonus in birthday_bonuses:
                end = datetime.strptime(bonus[9].replace("\r", ""), "%Y-%m-%d")
                end = end.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
                if end == current:
                    msg = (
                        f"{birthday_members}\n{birthday_total}% | "
                        f"{birthday_bonus_start.strftime('%B %d').replace(' 0', ' ')}"
                        f" - {end.strftime('%B %d').replace(' 0', ' ')}"
                        f" | End <t:{int(current.timestamp())}:R>\n"
                    )
                    notify_end.append(msg)

                    for bonus in rebum_bonuses:
                        start = datetime.strptime(bonus[8], "%Y-%m-%d")
                        start = datetime.now(ZoneInfo("Asia/Tokyo")).replace(
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
                                for x in (start, last_birthday_end, last_birthday_start)
                                if x is not None
                            ]
                        )

                        song_total = birthday_total + int(
                            bonus[1].replace("%", "").replace("\r", "")
                        )
                        album_name = bonus[4].replace("\r", "")
                        song_name = bonus[5].replace("\r", "")
                        song_duration = bonus[6].replace("\r", "")

                        msg = (
                            f"{album_name} - {song_name} ({song_duration})\n"
                            f"{song_total}% | "
                            f"{song_bonus_start.strftime('%B %d').replace(' 0', ' ')}"
                            f" - {end.strftime('%B %d').replace(' 0', ' ')}"
                            f" | End <t:{int(current.timestamp())}:R>\n"
                        )
                        notify_end.append(msg)

                    rebum_bonuses = []
                    break

        for bonus in album_bonuses:
            start = datetime.strptime(bonus[8].replace("\r", ""), "%Y-%m-%d")
            start = start.replace(tzinfo=ZoneInfo("Asia/Tokyo"))

            if start == current:
                end = datetime.strptime(bonus[9].replace("\r", ""), "%Y-%m-%d")
                end = end.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
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
                    bonus[1].replace("%", "").replace("\r", "")
                )
                album_name = bonus[4].replace("\r", "")
                song_name = bonus[5].replace("\r", "")
                song_duration = bonus[6].replace("\r", "")

                msg = (
                    f"{album_name} - {song_name} ({song_duration})\n"
                    f"{song_total}% | "
                    f"{song_bonus_start.strftime('%B %d').replace(' 0', ' ')} - "
                    f"{song_bonus_end.strftime('%B %d').replace(' 0', ' ')}"
                    f" | Available <t:{int(current.timestamp())}:R>\n"
                )
                notify_start.append(msg)

        for bonus in rebum_bonuses:
            end = datetime.strptime(bonus[9].replace("\r", ""), "%Y-%m-%d")
            end = end.replace(tzinfo=ZoneInfo("Asia/Tokyo"))

            if end == current:
                start = datetime.strptime(bonus[8].replace("\r", ""), "%Y-%m-%d")
                start = start.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
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
                    bonus[1].replace("%", "").replace("\r", "")
                )
                album_name = bonus[4].replace("\r", "")
                song_name = bonus[5].replace("\r", "")
                song_duration = bonus[6].replace("\r", "")

                msg = (
                    f"{album_name} - {song_name} ({song_duration})\n"
                    f"{song_total}% | "
                    f"{song_bonus_start.strftime('%B %d').replace(' 0', ' ')} - "
                    f"{song_bonus_end.strftime('%B %d').replace(' 0', ' ')}"
                    f" | End <t:{int(current.timestamp())}:R>\n"
                )
                notify_end.append(msg)

        print(artist)
        print("Start: ", end="")
        pprint(notify_start)
        print("End: ", end="")
        pprint(notify_end)
    sleep(2)
