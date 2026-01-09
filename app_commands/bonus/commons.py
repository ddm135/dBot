from datetime import datetime
from pathlib import Path

import discord

from statics.consts import BONUS_OFFSET, GAMES

from .types import BonusDict

STEP = 5


def bonus_top_embeds(
    game: str,
    bonuses: dict[str, list[BonusDict]],
    current_date: datetime,
    last_date: datetime,
    icon: str | Path | None,
) -> list[discord.Embed]:
    game_details = GAMES[game]
    embeds: list[discord.Embed] = []
    author = f"{game_details["name"]} - Top Bonuses"
    embeds.append(discord.Embed(color=game_details["color"]))
    embeds[-1].set_author(
        name=author,
        icon_url="attachment://icon.png" if isinstance(icon, Path) else icon,
    )
    embed_count = len(author)
    embed_field_count = 0

    for artist_name, _bonuses in bonuses.items():
        field_name = (
            artist_name.replace(r"*", r"\*").replace(r"_", r"\_").replace(r"`", r"\`")
        )
        field_value = ""
        field_name_count = len(field_name)
        field_value_count = 0

        for bonus in _bonuses:
            text = (
                f"> **{"~~" if bonus["bonusEnd"] < current_date
                       else "" if bonus["bonusStart"] > current_date
                       else ":white_check_mark: "}"
                f"{bonus["members"].replace(r"*", r"\*")
                    .replace(r"_", r"\_").replace(r"`", r"\`")
                    if bonus["members"]
                    and bonus["artist"] != bonus["members"]
                    else ""}"
                f"{": " if not artist_name
                    or bonus["members"] and bonus["artist"] != bonus["members"]
                    else ""}"
                f"{bonus["song"].replace(r"*", r"\*")
                    .replace(r"_", r"\_").replace(r"`", r"\`")
                    if bonus["song"]
                    else "All Songs :birthday:"}"
                f"{"" if not bonus["song"]
                    else " :cd:" if bonus["bonusAmount"] == 3
                    else " :birthday: :dvd:"}"
                f"{"~~" if bonus["bonusEnd"] < current_date else ""}**\n"
                f"> {"~~" if bonus["bonusEnd"] < current_date else ""}"
                f"{bonus["bonusAmount"]}% | "
                f"{bonus["bonusStart"].strftime("%B %d").replace(" 0", " ")} - "
                f"{bonus["bonusEnd"].strftime("%B %d").replace(" 0", " ")} | "
                f"{f"{bonus["maxScore"]:,} | " if bonus["maxScore"] else ""}"
                f"{"Expired" if bonus["bonusEnd"] < current_date
                    else f"Available <t:{int(bonus["bonusStart"].timestamp())}:R>"
                    if bonus["bonusStart"] > current_date
                    else f"Ends <t:"
                    f"{int((bonus["bonusEnd"] + BONUS_OFFSET).timestamp())}:R>"}"
                f"{" :bangbang:" if bonus["bonusStart"] == last_date else ""}"
                f"{"~~" if bonus["bonusEnd"] < current_date else ""}\n"
            )
            text_count = len(text)

            if (
                embed_count + field_name_count + field_value_count + text_count > 6000
                or embed_field_count > 25
            ):
                embeds.append(discord.Embed(color=game_details["color"]))
                embed_count = 0
                embed_field_count = 0
            if field_value_count + text_count > 1024:
                embeds[-1].add_field(name=field_name, value=field_value, inline=False)
                embed_count += field_name_count + field_value_count
                embed_field_count += 1

                field_name = ""
                field_value = ""
                field_name_count = 0
                field_value_count = 0

            field_value += text
            field_value_count += text_count

        if (
            embed_count + field_name_count + field_value_count > 6000
            or embed_field_count > 25
        ):
            embeds.append(discord.Embed(color=game_details["color"]))
            embed_count = 0
            embed_field_count = 0

        embeds[-1].add_field(name=field_name, value=field_value, inline=False)
        embed_count += field_name_count + field_value_count
        embed_field_count += 1

    page_count = len(embeds)
    if page_count == 1 and not embed_field_count:
        embeds[1].add_field(name="None", value="", inline=False)
    for index, embed in enumerate(embeds, 1):
        embed.set_footer(text=f"Page {index}/{page_count}")

    return embeds
