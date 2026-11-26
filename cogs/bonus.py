"""``/bonus``: birthday and anniversary bonuses, and pings for them."""

from datetime import date
from enum import Enum
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands

from cogs.common import (
    NO_DATA,
    Itr,
    choose_artist,
    deck_autocomplete,
    deck_of,
    game_choices,
    has_bonuses,
    parse_code,
    selected_game,
)
from games.bonus.entries import deck_entries, max_score, top_scores
from games.bonus.events import BonusCalendar
from games.data.decks import Deck
from games.index import Index
from games.registry import GAMES
from ui.bonus import (
    DeckEntries,
    WeekRange,
    list_embed,
    max_embed,
    month_range,
    pings_embed,
    top_embeds,
    week_range,
    year_range,
)
from ui.images import Upload, files
from ui.pages import Paginator, page_count
from ui.text import md

if TYPE_CHECKING:
    from bot import dBot

PER_PAGE = 5


class TimeRange(Enum):
    """The periods ``/bonus list`` can show, as a user picks them."""

    CURRENT_WEEK = "Current Week"
    NEXT_WEEK = "Next Week"
    CURRENT_MONTH = "Current Month"
    NEXT_MONTH = "Next Month"
    THIS_YEAR = "This Year"
    RIGHT_NOW = "Right Now"

    def resolve(self, today: date) -> WeekRange:
        """The first and last day of this range as seen from ``today``."""
        match self:
            case TimeRange.CURRENT_WEEK:
                return week_range(today)
            case TimeRange.NEXT_WEEK:
                return week_range(today, weeks_ahead=1)
            case TimeRange.CURRENT_MONTH:
                return month_range(today)
            case TimeRange.NEXT_MONTH:
                return month_range(today, months_ahead=1)
            case TimeRange.THIS_YEAR:
                return year_range(today)
            case TimeRange.RIGHT_NOW:
                return WeekRange(today, today)


TIME_CHOICES = [app_commands.Choice(name=t.value, value=t.name) for t in TimeRange]


TIME_CHOICES = [app_commands.Choice(name=t.value, value=t.name) for t in TimeRange]


def collect(
    index: Index,
    calendar_: BonusCalendar,
    window: WeekRange,
    only: Deck | None,
) -> list[DeckEntries]:
    """The bonus entries of the main decks (or just ``only``) in a window; decks with none
    are left out.
    """
    decks = [only] if only else [d for d in index.decks if d.is_main]
    found = []
    for deck in decks:
        entries = deck_entries(deck, calendar_, window.first, window.last)
        if entries:
            found.append(DeckEntries(deck, entries))
    return found


def scores_by_deck(index: Index, items: list[DeckEntries], live: int) -> dict[int, int]:
    """The best score each main deck can reach: its best bonus, or none."""
    best = {item.deck.code: item.best(index, live) for item in items}
    return {
        deck.code: best.get(deck.code) or index.deck_max_score(deck.code) + live
        for deck in index.decks
        if deck.is_main and index.deck_max_score(deck.code)
    }


def highest_only(
    index: Index, items: list[DeckEntries], live: int
) -> list[DeckEntries]:
    """Every deck with only its best-scoring entries, best decks first.

    Entries that tie for a deck's best all stay.
    """
    result = []
    for item in items:
        best = item.best(index, live)
        base = index.deck_max_score(item.deck.code)
        entries = [e for e in item.entries if max_score(base, e.total, live) == best]
        result.append(DeckEntries(item.deck, entries))
    result.sort(key=lambda i: -i.best(index, live))
    return result


class TopView(Paginator):
    """The weekly top bonuses: highest only or all, and the max score."""

    def __init__(
        self,
        owner: discord.abc.User,
        pages: dict[str, list[discord.Embed]],
        max_page: discord.Embed,
    ) -> None:
        self.sets = pages
        self.max_page = max_page
        self.mode = "highest"
        self.showing_max = False
        super().__init__(owner, self._render, len(pages["highest"]))
        self._sync_buttons()

    def _render(self, page: int, pages: int) -> discord.Embed:
        if self.showing_max:
            return self.max_page
        return self.sets[self.mode][page - 1]

    def _sync_buttons(self) -> None:
        self.highest_button.disabled = self.mode == "highest" and not self.showing_max
        self.all_button.disabled = self.mode == "all" and not self.showing_max
        self.max_button.disabled = self.showing_max

    async def _switch(
        self,
        interaction: discord.Interaction[Any],
        *,
        mode: str | None = None,
        show_max: bool = False,
    ) -> None:
        self.showing_max = show_max
        if mode:
            self.mode = mode
        self.pages = 1 if show_max else len(self.sets[self.mode])
        self.page = 1
        self._sync_buttons()
        await self.show(interaction)

    @discord.ui.button(
        label="Highest Bonuses Only", style=discord.ButtonStyle.secondary, row=1
    )
    async def highest_button(
        self, interaction: discord.Interaction[Any], _: discord.ui.Button[Any]
    ) -> None:
        await self._switch(interaction, mode="highest")

    @discord.ui.button(label="All Bonuses", style=discord.ButtonStyle.secondary, row=1)
    async def all_button(
        self, interaction: discord.Interaction[Any], _: discord.ui.Button[Any]
    ) -> None:
        await self._switch(interaction, mode="all")

    @discord.ui.button(label="Max Score", style=discord.ButtonStyle.secondary, row=1)
    async def max_button(
        self, interaction: discord.Interaction[Any], _: discord.ui.Button[Any]
    ) -> None:
        await self._switch(interaction, show_max=True)


class Bonus(commands.Cog):
    """``/bonus`` and ``/bonus ping``: lists, the weekly top, the live theme bonus,
    and the subscriptions and delivery times of bonus pings.
    """

    bonus = app_commands.Group(
        name="bonus", description="Birthday and anniversary bonuses."
    )
    ping = app_commands.Group(
        name="ping", description="Get pinged about bonuses.", parent=bonus
    )

    def __init__(self, bot: dBot) -> None:
        self.bot = bot

    # -- helpers -------------------------------------------------------------

    async def _context(
        self, itr: Itr, key: str
    ) -> tuple[Index, BonusCalendar, str | None] | None:
        await self.bot.indexes.warm(key)  # off the event loop
        index = self.bot.indexes.get(key)
        calendar_ = self.bot.indexes.current_calendar(key)
        if index is None or calendar_ is None:
            await itr.followup.send(NO_DATA)
            return None
        icon = self.bot.games.get(key).icon_url
        return index, calendar_, icon

    async def _live(
        self, itr: Itr, index: Index, key: str, given: int | None
    ) -> int | None:
        """The live theme bonus to use; None after reporting an invalid value."""
        if given is None:
            return min(
                await self.bot.db.live_themes.get(itr.user.id, key),
                index.live_theme_max,
            )
        if given > index.live_theme_max:
            await itr.followup.send(
                f"The live theme bonus can be at most {index.live_theme_max:,}."
            )
            return None
        return given

    # -- /bonus list ---------------------------------------------------------

    @bonus.command(name="list")
    @app_commands.choices(game=game_choices(has_bonuses), time=TIME_CHOICES)
    @app_commands.autocomplete(artist=deck_autocomplete)
    async def list_(
        self,
        itr: Itr,
        game: app_commands.Choice[str],
        artist: str | None = None,
        time: app_commands.Choice[str] | None = None,
        live_theme_bonus: app_commands.Range[int, 0] | None = None,
    ) -> None:
        """View bonuses for a game, an artist, and a time range.

        Parameters
        ----------
        game: Game
        artist: Artist/Album
        time: Time range (default: this year)
        live_theme_bonus: Your live theme bonus (default: your saved one)
        """
        await itr.response.defer()
        if not (ctx := await self._context(itr, game.value)):
            return
        index, calendar_, icon = ctx
        deck = None
        uploads: list[Upload] = []
        if artist is not None:
            if (
                chosen := await choose_artist(self.bot, itr, index, artist, icon)
            ) is None:
                return
            deck, icon, uploads = chosen
        if (live := await self._live(itr, index, game.value, live_theme_bonus)) is None:
            return

        today = self.bot.indexes.today(index.game)
        window = (TimeRange[time.value] if time else TimeRange.THIS_YEAR).resolve(today)
        items = collect(index, calendar_, window, deck)
        rows = [(item.deck, e) for item in items for e in item.entries]
        rows.sort(key=lambda pair: (pair[1].end, pair[1].start, pair[0].code))
        if not rows:
            await itr.followup.send("No bonuses found.")
            return

        first_open = next((i for i, (_, e) in enumerate(rows) if e.end >= today), 0)
        pages = page_count(len(rows), PER_PAGE)

        def render(page: int, total: int) -> discord.Embed:
            return list_embed(
                index,
                deck,
                rows,
                first=window.first,
                last=window.last,
                today=today,
                live_theme=live,
                icon=icon,
                page=page,
                pages=total,
                per_page=PER_PAGE,
            )

        view = Paginator(itr.user, render, pages, page=first_open // PER_PAGE + 1)
        await view.start(itr, files=files(uploads))

    # -- /bonus top ----------------------------------------------------------

    @bonus.command()
    @app_commands.choices(
        game=game_choices(lambda g: has_bonuses(g) and bool(g.base_score))
    )
    async def top(
        self,
        itr: Itr,
        game: app_commands.Choice[str],
        live_theme_bonus: app_commands.Range[int, 0] | None = None,
    ) -> None:
        """View the highest bonuses of the current week.

        Parameters
        ----------
        game: Game
        live_theme_bonus: Your live theme bonus (default: your saved one)
        """
        await itr.response.defer()
        if not (ctx := await self._context(itr, game.value)):
            return
        index, calendar_, icon = ctx
        if (live := await self._live(itr, index, game.value, live_theme_bonus)) is None:
            return
        today = self.bot.indexes.today(index.game)
        window = week_range(today)
        items = collect(index, calendar_, window, None)
        scores = scores_by_deck(index, items, live)
        items.sort(key=lambda i: -i.best(index, live))

        def pages(shown: list[DeckEntries]) -> list[discord.Embed]:
            return top_embeds(
                index,
                shown,
                today=today,
                last_day=window.last,
                live_theme=live,
                icon=icon,
            )

        ranked, total = top_scores(scores)
        view = TopView(
            itr.user,
            {"highest": pages(highest_only(index, items, live)), "all": pages(items)},
            max_embed(index, ranked, total, icon),
        )
        view.message = await itr.followup.send(embed=view.embed(), view=view, wait=True)

    # -- /bonus live_theme ---------------------------------------------------

    @bonus.command()
    @app_commands.choices(game=game_choices(has_bonuses))
    async def live_theme(
        self,
        itr: Itr,
        game: app_commands.Choice[str],
        amount: app_commands.Range[int, 0],
    ) -> None:
        """Save your live theme bonus, so it is used in bonus scores.

        Parameters
        ----------
        game: Game
        amount: Your live theme bonus
        """
        await itr.response.defer(ephemeral=True)  # the database can be slow
        index = self.bot.indexes.get(game.value)
        if index is None:
            await itr.followup.send(NO_DATA, ephemeral=True)
            return
        if amount > index.live_theme_max:
            await itr.followup.send(
                f"The live theme bonus can be at most {index.live_theme_max:,}.",
                ephemeral=True,
            )
            return
        await self.bot.db.live_themes.set(itr.user.id, game.value, amount)
        await itr.followup.send(
            f"Saved your {index.game.name} live theme bonus as {amount:,}.",
            ephemeral=True,
        )

    # -- /bonus ping ---------------------------------------------------------

    @ping.command(name="add")
    @app_commands.choices(game=game_choices(has_bonuses))
    @app_commands.autocomplete(artist=deck_autocomplete)
    async def ping_add(
        self, itr: Itr, game: app_commands.Choice[str], artist: str
    ) -> None:
        """Get pinged when an artist's bonuses start or end.

        Parameters
        ----------
        game: Game
        artist: Artist/Album
        """
        await itr.response.defer(ephemeral=True)  # the database can be slow
        index = self.bot.indexes.get(game.value)
        deck = deck_of(index, artist) if index else None
        if deck is None:
            await itr.followup.send("Artist not found.", ephemeral=True)
            return
        added = await self.bot.db.bonus_pings.subscribe(
            itr.user.id, game.value, deck.code
        )
        text = (
            md(t"You will be pinged about **{deck.name}** bonuses in {game.name}.")
            if added
            else md(t"You are already pinged about **{deck.name}** bonuses.")
        )
        await itr.followup.send(text, ephemeral=True)

    async def _subscribed_autocomplete(
        self, itr: Itr, current: str
    ) -> list[app_commands.Choice[str]]:
        key = selected_game(itr)
        index = self.bot.indexes.get(key) if key else None
        if not key or index is None:
            return []
        wanted = current.casefold()
        choices = []
        for code in await self.bot.db.bonus_pings.decks_of(itr.user.id, key):
            deck = index.decks.decks.get(code)
            if deck and wanted in deck.label.casefold():
                choices.append(
                    app_commands.Choice(name=deck.label[:100], value=str(code))
                )
        return choices[:25]

    @ping.command(name="remove")
    @app_commands.choices(game=game_choices(has_bonuses))
    @app_commands.autocomplete(artist=_subscribed_autocomplete)
    async def ping_remove(
        self, itr: Itr, game: app_commands.Choice[str], artist: str
    ) -> None:
        """Stop getting pinged about an artist's bonuses.

        Parameters
        ----------
        game: Game
        artist: Artist/Album
        """
        await itr.response.defer(ephemeral=True)  # the database can be slow
        code = parse_code(artist)
        removed = code is not None and await self.bot.db.bonus_pings.unsubscribe(
            itr.user.id, game.value, code
        )
        await itr.followup.send(
            "Removed." if removed else "You were not pinged about that artist.",
            ephemeral=True,
        )

    @ping.command(name="list")
    async def ping_list(self, itr: Itr) -> None:
        """List the artists you get bonus pings for."""
        await itr.response.defer(ephemeral=True)  # the database can be slow
        embeds: list[discord.Embed] = []
        for game in GAMES.values():
            if not has_bonuses(game):
                continue
            index = self.bot.indexes.get(game.key)
            codes = await self.bot.db.bonus_pings.decks_of(itr.user.id, game.key)
            names = [
                (index.group_name(c) if index else None) or f"Deck {c}" for c in codes
            ]
            if names:
                icon = self.bot.games.get(game.key).icon_url
                embeds.append(pings_embed(game.name, game.color, names, icon))
        prefs = (await self.bot.db.bonus_pings.preferences([itr.user.id]))[itr.user.id]
        timing = f"-# Start pings: {_hours(prefs.start_hours)}. End pings: {_hours(prefs.end_hours)}."
        if not embeds:
            await itr.followup.send(
                f"You have no bonus pings.\n{timing}", ephemeral=True
            )
            return
        await itr.followup.send(timing, embeds=embeds, ephemeral=True)

    @ping.command(name="time")
    async def ping_time(
        self,
        itr: Itr,
        start: app_commands.Range[int, 0, 47] | None = None,
        end: app_commands.Range[int, 0, 47] | None = None,
    ) -> None:
        """Choose how long before a day begins you get pinged (up to 47). 0 turns it off.

        Parameters
        ----------
        start: Hours before the day a bonus starts
        end: Hours before the day a bonus ends
        """
        await itr.response.defer(ephemeral=True)  # the database can be slow
        prefs = await self.bot.db.bonus_pings.set_preferences(
            itr.user.id, start_hours=start, end_hours=end
        )
        await itr.followup.send(
            f"Start pings: {_hours(prefs.start_hours)}. End pings: {_hours(prefs.end_hours)}.",
            ephemeral=True,
        )


def _hours(hours: int) -> str:
    if not hours:
        return "off"
    return f"{hours} hour{'s' if hours != 1 else ''} before"


async def setup(bot: dBot) -> None:
    await bot.add_cog(Bonus(bot))
