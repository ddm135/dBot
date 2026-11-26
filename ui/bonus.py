"""Embeds and text for bonus entries and pings, laid out as v0 did.

Pure formatting: it takes the bonus data and builds strings and embeds, so
it can be tested without Discord.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import discord

from games.bonus.entries import BonusEntry, max_score
from games.bonus.notices import NoticeLine, Section
from games.bonus.periods import MemberBonus
from games.charts.song_stats import SongStat
from games.data.decks import Deck
from games.index import Index
from ui.text import escape, md, month_day, timestamp

MAX_SONG_NAMES = 3
EMBED_CHARS = 6000
EMBED_FIELDS = 25
FIELD_CHARS = 1024
BLANK = "\u200b"  # an empty-looking name for the continuation of a field
MAX_POSITIONS = 5


@dataclass(frozen=True, slots=True)
class DeckEntries:
    """A deck with its bonus entries in a window."""

    deck: Deck
    entries: list[BonusEntry]

    def best(self, index: Index, live: int) -> int:
        """The best score the deck can reach with one of its entries."""
        base = index.deck_max_score(self.deck.code)
        return max((max_score(base, e.total, live) for e in self.entries), default=0)


def midnight(index: Index, day: date) -> datetime:
    """The start of ``day`` in the game's timezone."""
    return datetime.combine(day, time(), tzinfo=index.game.timezone)


# -- one entry -------------------------------------------------------------------


def song_names(deck: Deck, entry: BonusEntry) -> str:
    """The songs of an entry: all, a few by name, or a few and a count."""
    if entry.all_songs:
        return "All Songs"
    by_code = {s.code: s for s in deck.songs}
    names = [escape(by_code[c].label) for c in entry.song_codes if c in by_code]
    if len(names) <= MAX_SONG_NAMES:
        return ", ".join(names)
    return ", ".join(names[:MAX_SONG_NAMES]) + f" +{len(names) - MAX_SONG_NAMES} more"


def entry_icons(entry: BonusEntry) -> str:
    """The emoji that say what an entry is for: a birthday, a release, or both."""
    if entry.has_release:
        return ":birthday: :dvd:" if entry.members else ":cd:"
    return ":birthday:"


def percent_text(total: int, before: int | None = None) -> str:
    """``5%``, or ``7% -> 5%`` for a bonus that replaces another."""
    return f"{before}% -> {total}%" if before is not None else f"{total}%"


def entry_prefix(entry: BonusEntry, today: date) -> str:
    """What goes before an entry's name: struck through when over, a check mark when
    active.
    """
    match entry.status(today):
        case "expired":
            return "~~"
        case "upcoming":
            return ""
        case _:
            return ":white_check_mark: "


def member_names(members: Iterable[MemberBonus], index: Index) -> str:
    """Members joined with `` + ``; one from another deck is followed by that deck
    (``Jin (from TWICE)``).
    """
    names = []
    for member in members:
        group = index.group_name(member.group_code) if member.group_code else None
        names.append(f"{member.name} (from {group})" if group else member.name)
    return " + ".join(names)


def entry_name(
    entry: BonusEntry,
    deck: Deck,
    index: Index,
    today: date,
    *,
    show_deck: bool = False,
) -> str:
    """The first line of an entry.

    ``<prefix>[**deck**] [members: ]<songs> <icons>``. The members are named
    only for a birthday on its own, and not when they are the deck itself.
    """
    own = "" if entry.has_release else " + ".join(m.name for m in entry.members)
    members = member_names(entry.members, index) if own and own != deck.name else ""
    name = entry_prefix(entry, today)
    if show_deck:
        name += md(t"**{deck.name}**") + (" " if members else "")
    name += escape(members)
    name += ": " if show_deck or members else ""
    name += song_names(deck, entry) + " " + entry_icons(entry)
    return name + ("~~" if entry.status(today) == "expired" else "")


def entry_value(
    entry: BonusEntry,
    deck: Deck,
    index: Index,
    *,
    today: date,
    last_day: date | None = None,
    live_theme: int = 0,
) -> str:
    """The second line: ``5% | October 23 - October 28 | 6,844,650 | Ends in 3 days``."""
    expired = entry.status(today) == "expired"
    parts = [
        percent_text(entry.total, entry.before),
        f"{month_day(entry.start)} - {month_day(entry.end)}",
    ]
    score = max_score(index.deck_max_score(deck.code), entry.total, live_theme)
    if score:
        parts.append(f"{score:,}")
    match entry.status(today):
        case "expired":
            parts.append("Expired")
        case "upcoming":
            parts.append(f"Available {timestamp(midnight(index, entry.start))}")
        case _:
            end = midnight(index, entry.end + timedelta(days=1))
            parts.append(f"Ends {timestamp(end)}")
    value = " | ".join(parts)
    if last_day is not None and entry.start == last_day:
        value += " :bangbang:"
    return f"~~{value}~~" if expired else value


# -- /bonus list -------------------------------------------------------------------


def list_embed(
    index: Index,
    deck: Deck | None,
    rows: list[tuple[Deck, BonusEntry]],
    *,
    first: date,
    last: date,
    today: date,
    live_theme: int,
    icon: str | None,
    page: int,
    pages: int,
    per_page: int,
) -> discord.Embed:
    """A page of ``/bonus list``: the entries of one artist or all, with their dates and
    scores.
    """
    shown = rows[(page - 1) * per_page : page * per_page]
    title = escape(deck.name) if deck else "All Bonuses"
    embed = discord.Embed(
        title=f"{title} ({month_day(first)} - {month_day(last)})",
        description=None if shown else "None",
        color=index.game.color,
    )
    embed.set_author(name=f"{index.game.name} - Bonus Info", icon_url=icon)
    embed.set_footer(text=f"Page {page}/{pages}")
    for entry_deck, entry in shown:
        embed.add_field(
            name=entry_name(entry, entry_deck, index, today, show_deck=deck is None),
            value=entry_value(
                entry,
                entry_deck,
                index,
                today=today,
                last_day=last,
                live_theme=live_theme,
            ),
            inline=False,
        )
    return embed


# -- /bonus top --------------------------------------------------------------------


def top_entry_text(
    entry: BonusEntry,
    deck: Deck,
    index: Index,
    *,
    today: date,
    last_day: date,
    live_theme: int,
) -> str:
    """One entry of the weekly top as text: its name, percentage, dates and score."""
    name = entry_name(entry, deck, index, today)
    # The name line is bold; the prefix and the strike-through sit inside it.
    value = entry_value(
        entry, deck, index, today=today, last_day=last_day, live_theme=live_theme
    )
    return f"> **{name}**\n> {value}\n"


def top_embeds(
    index: Index,
    items: list[DeckEntries],
    *,
    today: date,
    last_day: date,
    live_theme: int,
    icon: str | None,
) -> list[discord.Embed]:
    """One field per deck, packed into as few embeds as Discord's limits allow."""
    color = index.game.color
    author = f"{index.game.name} - Top Bonuses"

    def fresh() -> discord.Embed:
        embed = discord.Embed(color=color)
        embed.set_author(name=author, icon_url=icon)
        return embed

    embeds = [fresh()]
    embed_chars, embed_fields = len(author), 0
    for item in items:
        name = escape(item.deck.name)
        value, value_chars, name_chars = "", 0, len(name)
        base = index.deck_max_score(item.deck.code)
        entries = sorted(
            item.entries, key=lambda e: -max_score(base, e.total, live_theme)
        )
        for entry in entries:
            text = top_entry_text(
                entry,
                item.deck,
                index,
                today=today,
                last_day=last_day,
                live_theme=live_theme,
            )
            if (
                embed_chars + name_chars + value_chars + len(text) > EMBED_CHARS
                or embed_fields >= EMBED_FIELDS
            ):
                embeds.append(fresh())
                embed_chars, embed_fields = 0, 0
            if value_chars + len(text) > FIELD_CHARS:
                embeds[-1].add_field(name=name, value=value, inline=False)
                embed_chars += name_chars + value_chars
                embed_fields += 1
                name, value, name_chars, value_chars = BLANK, "", 1, 0
            value += text
            value_chars += len(text)
        if (
            embed_chars + name_chars + value_chars > EMBED_CHARS
            or embed_fields >= EMBED_FIELDS
        ):
            embeds.append(fresh())
            embed_chars, embed_fields = 0, 0
        embeds[-1].add_field(name=name, value=value, inline=False)
        embed_chars += name_chars + value_chars
        embed_fields += 1
    if not items:
        embeds[0].description = "None"
    for number, embed in enumerate(embeds, 1):
        embed.set_footer(text=f"Page {number}/{len(embeds)}")
    return embeds


def max_embed(
    index: Index,
    ranked: dict[int, list[int]],
    total: int,
    icon: str | None,
) -> discord.Embed:
    """The week's best scores: ``Top 1-3: 6,844,650`` and the decks that share it."""
    embed = discord.Embed(
        title="Max Score of This Week",
        description=f"**{total:,}**",
        color=index.game.color,
    )
    embed.set_author(name=f"{index.game.name} - Top Bonuses", icon_url=icon)
    position = 1
    for score, codes in ranked.items():
        last = min(position + len(codes) - 1, MAX_POSITIONS)
        label = (
            f"**Top {position}"
            + (f"-{last}" if last != position else "")
            + f"**: {score:,}"
        )
        names = ", ".join(escape(index.group_name(c) or str(c)) for c in codes)
        embed.add_field(name=label, value=names, inline=False)
        if last >= MAX_POSITIONS:
            break
        position = last + 1
    return embed


def pings_embed(
    index_game_name: str, color: int, decks: list[str], icon: str | None
) -> discord.Embed:
    """``/bonus ping list``: a game and the artists the user follows."""
    description = "\n".join(md(t"- {name}") for name in decks) or "None"
    embed = discord.Embed(description=description, color=color)
    embed.set_author(name=index_game_name, icon_url=icon)
    return embed


# -- bonus pings --------------------------------------------------------------------


def notice_text(
    line: NoticeLine,
    deck: Deck,
    index: Index,
    stats: dict[int, SongStat] | None = None,
) -> str:
    """One entry of a ping, as a block quote:

    ``> YUTA + WINWIN - **All Songs**`` or ``> Album - **Song** (3:21)``, then
    ``> 4% | October 25 - October 29``.
    """
    window = f"> {percent_text(line.total, line.before)} | {month_day(line.start)} - {month_day(line.end)}\n"
    if not line.has_release:
        who = escape(member_names(line.members, index))
        by_code = {s.code: s for s in deck.songs}
        songs = (
            "All Songs"
            if line.all_songs
            else ", ".join(
                escape(by_code[c].label) for c in line.song_codes if c in by_code
            )
        )
        return f"> {who} - **{songs}**\n{window}"
    song = next((s for s in deck.songs if s.code == line.song_codes[0]), None)
    if song is None:
        return ""
    stat = (stats or {}).get(song.code)
    duration = f" ({stat.duration})" if stat else ""
    album = song.album or deck.name
    return md(t"> {album} - **{song.label}**{duration}\n{window}")


def notice_embed(
    index: Index,
    deck: Deck,
    day: date,
    texts: dict[Section, list[str]],
    icon: str | None,
) -> discord.Embed:
    """A deck's ping: what becomes available and what ends, under its name."""
    embed = discord.Embed(color=index.game.color)
    embed.set_author(name=escape(deck.name), icon_url=icon)
    start = midnight(index, day)
    headers: dict[Section, str] = {
        "start": f"Available {timestamp(start)} :green_circle:",
        "drop": f"Ends {timestamp(start)} :orange_circle:",  # the higher bonus
        "end": f"Ends {timestamp(start + timedelta(days=1))} :orange_circle:",
    }
    for category in ("start", "drop", "end"):
        for number, chunk in enumerate(chunks(texts.get(category, []))):
            embed.add_field(
                name=headers[category] if not number else BLANK,
                value=chunk,
                inline=False,
            )
    return embed


def chunks(parts: list[str], limit: int = FIELD_CHARS) -> list[str]:
    """Join parts into values shorter than ``limit``, never splitting a part."""
    result: list[str] = []
    current = ""
    for part in parts:
        if current and len(current) + len(part) >= limit:
            result.append(current)
            current = ""
        current += part
    if current:
        result.append(current)
    return result


# -- time ranges ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WeekRange:
    """A range of days, first to last, inclusive."""

    first: date
    last: date  # inclusive


def week_range(today: date, *, weeks_ahead: int = 0) -> WeekRange:
    """Monday to the following Monday, as v0 showed it (8 days)."""
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=weeks_ahead)
    return WeekRange(monday, monday + timedelta(days=7))


def month_range(today: date, *, months_ahead: int = 0) -> WeekRange:
    """The month of ``today``, or one ``months_ahead``."""
    month = today.month - 1 + months_ahead
    first = date(today.year + month // 12, month % 12 + 1, 1)
    nxt = date(first.year + (first.month // 12), first.month % 12 + 1, 1)
    return WeekRange(first, nxt - timedelta(days=1))


def year_range(today: date) -> WeekRange:
    """The year of ``today``."""
    return WeekRange(date(today.year, 1, 1), date(today.year, 12, 31))
