"""World-record embeds, laid out as v0 did."""

import math
from datetime import datetime

import discord

from games.api.world_records import Record
from games.models import Game

from .pages import slice_page
from .text import escape

PER_PAGE = 10


def page_total(count: int) -> int:
    return math.ceil(count / PER_PAGE) or 1


def last_updated_text(updated: datetime | None) -> str:
    """`` · Last Updated: Monday, October 5, 2026, 4:03:09 KST`` (v0 also drops a
    zero in front of the hour)."""
    if updated is None:
        return ""
    stamp = updated.strftime(
        f" · Last Updated: %A, %B %d, %Y, %H:%M:%S {updated.tzname()}"
    )
    return stamp.replace(" 0", " ")


def _frame(
    game: Game,
    title: str,
    description: str,
    season: int,
    icon: str | None,
    page: int,
    pages: int,
    updated: datetime | None,
) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=game.color)
    embed.set_author(
        name=f"{game.name} - World Record (Season {season})", icon_url=icon
    )
    embed.set_footer(text=f"Page {page}/{pages}{last_updated_text(updated)}")
    return embed


def leaderboard_embed(
    game: Game,
    artist: str,
    song: str | None,
    season: int,
    records: tuple[Record, ...],
    updated: datetime | None,
    thumbnail: str | None,
    icon: str | None,
    page: int = 1,
) -> discord.Embed:
    """A song's (or, for weekly seasons, an artist's) top records."""
    shown = slice_page(records, page, PER_PAGE)
    title = escape(artist) + (f" - {escape(song)}" if song else "")
    description = (
        "\n".join(
            f"{r.rank}. **{escape(r.nickname)}** - {r.highscore:,}" for r in shown
        )
        or "None"
    )
    embed = _frame(
        game, title, description, season, icon, page, page_total(len(records)), updated
    )
    embed.set_thumbnail(url=thumbnail)
    return embed


def artist_embed(
    game: Game,
    artist: str,
    season: int,
    rows: list[tuple[str, Record | str]],
    updated: datetime | None,
    icon: str | None,
    page: int = 1,
) -> discord.Embed:
    """The top record of each song of an artist; a song with none says "None"."""
    shown = slice_page(rows, page, PER_PAGE)
    lines = []
    for song, record in shown:
        if isinstance(record, str):
            result = f"**{record}**"
        else:
            result = f"**{escape(record.nickname)}** - {record.highscore:,}"
        lines.append(f"- {escape(song)}: {result}")
    return _frame(
        game,
        escape(artist),
        "\n".join(lines) or "None",
        season,
        icon,
        page,
        page_total(len(rows)),
        updated,
    )
