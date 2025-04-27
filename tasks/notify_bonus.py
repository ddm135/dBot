from datetime import datetime, time
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

from statics.consts import GAMES, ME, ONE_DAY
from statics.helpers import get_sheet_data

if TYPE_CHECKING:
    from dBot import dBot


class NotifyBonus(commands.Cog):

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.notify_bonus.start()
        await super().cog_load()

    async def cog_unload(self) -> None:
        self.notify_bonus.cancel()
        await super().cog_unload()

    @tasks.loop(time=[time(hour=h) for h in range(24)])
    async def notify_bonus(self) -> None:
        for game, game_details in GAMES.items():
            if not game_details["bonusId"]:
                continue

            timezone = game_details["timezone"]
            current_date = datetime.now(tz=timezone)
            if current_date.hour != 23:
                continue

            game_name = game_details["name"]
            print(game_name)

            current_date = (
                current_date.replace(
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
                + ONE_DAY
            )
            initial_msg = (
                f"## Bonus Reminder for {game_name} on "
                f"<t:{int(current_date.timestamp())}:f>"
            )

            ping_columns = game_details["pingColumns"]
            ping_users_index = ping_columns.index("users")
            ping_artist_index = ping_columns.index("artist_name")
            ping_emblem_index = ping_columns.index("emblem")

            ping_data = get_sheet_data(
                game_details["pingId"], game_details["pingRange"]
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

            bonus_columns = game_details["bonusColumns"]
            member_name_index = bonus_columns.index("member_name")
            album_name_index = bonus_columns.index("album_name")
            song_name_index = bonus_columns.index("song_name")
            duration_index = bonus_columns.index("duration")
            bonus_start_index = bonus_columns.index("bonus_start")
            bonus_end_index = bonus_columns.index("bonus_end")
            bonus_amount_index = bonus_columns.index("bonus_amount")

            bonus_data = self.bot.bonus_data[game]
            artists = bonus_data.keys()
            for artist in artists:
                print(artist)
                artist_pings = next(
                    (ping for ping in ping_data if ping[ping_artist_index] == artist),
                    None,
                )
                if not artist_pings:
                    continue
                artist_ping_list = artist_pings[ping_users_index].split(",")
                artist_ping_list.remove("") if "" in artist_ping_list else None
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
                        last_birthday_end = end_date + ONE_DAY

                    if (
                        not next_birthday_start
                        and current_date < start_date
                        and bonus[member_name_index]
                    ):
                        next_birthday_start = start_date - ONE_DAY

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

                print(birthday_bonuses)
                print(album_bonuses)

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
                    for user_id in artist_ping_list:
                        user = await self.bot.fetch_user(int(user_id))
                        try:
                            if not game_ping_dict[user_id]:
                                await user.send(f"{initial_msg}")
                                game_ping_dict[user_id] = True
                            embed = discord.Embed(color=game_details["color"])
                            if notify_start:
                                embed.add_field(
                                    name=(
                                        f"Available <t:{int(current_date.timestamp())}"
                                        f":R> :green_circle:"
                                    ),
                                    value="".join(notify_start),
                                    inline=False,
                                )
                            if notify_end:
                                embed.add_field(
                                    name=(
                                        f"Ends <t:"
                                        f"{int((current_date + ONE_DAY).timestamp())}"
                                        f":R> :orange_circle:"
                                    ),
                                    value="".join(notify_end),
                                    inline=False,
                                )
                            embed.set_author(
                                name=artist.replace(r"*", r"\*").replace(r"_", r"\_"),
                                icon_url=artist_pings[ping_emblem_index] or None,
                            )

                            await user.send(embed=embed, silent=True)
                        except discord.Forbidden:
                            me = await self.bot.fetch_user(ME)
                            await me.send(
                                f"Failed to send bonus ping to {user.name} ({user.id})"
                                f" for {game_name} {artist}."
                            )
                        except discord.NotFound:
                            pass

    @notify_bonus.before_loop
    async def before_notify_bonus(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: "dBot") -> None:
    await bot.add_cog(NotifyBonus(bot))
