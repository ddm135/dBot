"""Derived, cached views of each game's tables.

The tables change at most hourly, so everything derived from them (the deck
index, score ceilings, the bonus calendar) is built once and reused until a
sync replaces the tables.
"""

import asyncio
import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING, Literal

from .bonuses import (
    DEFAULT_RULES,
    BonusCalendar,
    BonusRules,
    build_song_periods,
)
from .decks import (
    Deck,
    DeckIndex,
    Entry,
    build_deck_index,
    clean,
    entry_name,
    name_key,
)
from .fields import LOCALE_COLUMNS
from .models import Game, StringsConfig
from .scoring import DeckScore, deck_scores, live_theme_maximum, member_counts
from .strings import pick

if TYPE_CHECKING:
    from .service import DataService, State

logger = logging.getLogger(__name__)

SOURCE_TABLES = (
    "MusicData",
    "ArtistData",
    "GroupData",
    "AlbumData",
    "LocaleData",
    "LiveThemeData",
    "URLs",
)

CALENDAR_YEARS_BEFORE = 0
CALENDAR_YEARS_AFTER = 1  # so a window across New Year is always complete


@dataclass(frozen=True, slots=True, eq=False)
class Index:
    """Everything derived from one set of tables."""

    game: Game
    decks: DeckIndex
    scores: Mapping[int, DeckScore]
    live_theme_max: int
    artists: Mapping[str, Entry] = field(repr=False)
    locale: Mapping[str, Entry] = field(repr=False)
    urls: Mapping[str, Entry] = field(repr=False)
    music: Mapping[str, Entry] = field(repr=False)
    groups: Mapping[str, Entry] = field(repr=False, default_factory=dict)
    albums: Mapping[str, Entry] = field(repr=False, default_factory=dict)
    group_labels: Mapping[str, str] = field(repr=False, default_factory=dict)
    languages: tuple[str, ...] = ("enUS", "koKR")
    strings: Mapping[str, Mapping[str, str]] = field(repr=False, default_factory=dict)

    def string_names(self, key: str, code: object) -> list[str]:
        """Every language's text of a string-table key (``key`` holds ``{code}``)."""
        texts = self.strings.get(key.format(code=code), {})
        return [t for t in texts.values() if t]

    def group_name(self, code: int) -> str | None:
        """A deck name, even for a deck that has no songs."""
        deck = self.decks.decks.get(code)
        if deck:
            return deck.name
        group = self.groups.get(str(code))
        if not group:
            return None
        return self.group_labels.get(str(code)) or entry_name(
            self.locale, group, self.languages
        )

    def resolve_url(self, value: object) -> str | None:
        """A file reference from the tables as a URL, if it is one.

        Tables refer to files by code in ``URLs``; some games use catalog
        keys instead, which need the asset sync and give ``None`` here.
        """
        if isinstance(value, str) and value.startswith("http"):
            return value
        if isinstance(value, int):
            entry = self.urls.get(str(value))
            url = entry.get("url") if entry else None
            return url if isinstance(url, str) else None
        return None

    def emblem_url(self, deck_code: int) -> str | None:
        deck = self.decks.decks.get(deck_code)
        return self.resolve_url(deck.raw.get("emblemImage")) if deck else None

    def album_ref(self, song_code: int) -> object:
        """What names a song's album art: a table value, or a catalog key built
        from the album code for games that keep the art in the catalog."""
        song = self.decks.songs.get(song_code)
        if song is None:
            return None
        if song.raw.get("album"):
            return song.raw["album"]
        template = self.game.album_image_key
        code = song.raw.get("albumCode")
        if template and code and str(code) in self.albums:
            return template.format(code=code)
        return None

    def album_url(self, song_code: int) -> str | None:
        return self.resolve_url(self.album_ref(song_code))

    def album_color(self, song_code: int) -> int | None:
        """The album's colour. The table stores ``0xRRGGBBAA``; the alpha is dropped."""
        song = self.decks.songs.get(song_code)
        raw = song.raw.get("albumBgColor") if song else None
        return parse_color(raw)

    def deck_max_score(self, deck_code: int) -> int:
        score = self.scores.get(deck_code)
        return score.base if score else 0


def parse_color(raw: object) -> int | None:
    """``0xRRGGBBAA`` (or ``RRGGBBAA``) as ``0xRRGGBB``; None if it is not a colour."""
    if not isinstance(raw, str):
        return None
    text = raw.strip().removeprefix("0x").removeprefix("0X").removeprefix("#")
    if len(text) not in (6, 8):
        return None
    try:
        return int(text[:6], 16)
    except ValueError:
        return None


def _from_strings(
    game: Game,
    tables: Mapping[str, Mapping[str, Entry]],
    strings: Mapping[str, Mapping[str, str]],
    table: str,
    key: Callable[[StringsConfig], str],
) -> dict[str, str]:
    """The text the game's string table has for each code of a table."""
    config = game.strings
    if config is None:
        return {}
    found = {}
    for code in tables.get(table, {}):
        text = pick(strings, key(config).format(code=code), config.languages)
        if text:
            found[code] = clean(text) or text
    return found


def album_titles(
    game: Game,
    tables: Mapping[str, Mapping[str, Entry]],
    strings: Mapping[str, Mapping[str, str]],
) -> dict[str, str]:
    """Each album's title from the game's string table, where it has one."""
    return _from_strings(game, tables, strings, "AlbumData", lambda c: c.album_key)


def group_names(
    game: Game,
    tables: Mapping[str, Mapping[str, Entry]],
    strings: Mapping[str, Mapping[str, str]],
) -> dict[str, str]:
    """Each group's name from the game's string table, where it has one."""
    return _from_strings(game, tables, strings, "GroupData", lambda c: c.group_key)


def song_names(
    game: Game,
    tables: Mapping[str, Mapping[str, Entry]],
    strings: Mapping[str, Mapping[str, str]],
) -> dict[str, str]:
    """Each song's title from the game's string table, where it has one."""
    return _from_strings(game, tables, strings, "MusicData", lambda c: c.song_key)


def build_index(
    game: Game,
    tables: Mapping[str, Mapping[str, Entry]],
    strings: Mapping[str, Mapping[str, str]] | None = None,
    names: Mapping[tuple[NameKind, int], str] | None = None,
) -> Index | None:
    """``names`` holds ("deck" | "song", code) -> the name to show instead."""
    if not tables.get("MusicData"):
        return None
    shown = names or {}
    decks = build_deck_index(
        tables,
        game.timezone,
        album_decks=game.album_decks,
        album_titles=album_titles(game, tables, strings or {}),
        group_names=group_names(game, tables, strings or {}),
        song_names={
            **song_names(game, tables, strings or {}),
            **{str(c): n for (k, c), n in shown.items() if k == "song"},
        },
        languages=game.languages,
        deck_overrides={str(c): n for (k, c), n in shown.items() if k == "deck"},
    )
    scores = deck_scores(tables, game.base_score, list(decks.decks))
    counts = member_counts(tables.get("ArtistData", {}))
    return Index(
        game=game,
        decks=decks,
        scores=scores,
        live_theme_max=live_theme_maximum(tables, counts, set(decks.decks)),
        artists=tables.get("ArtistData", {}),
        locale=tables.get("LocaleData", {}),
        urls=tables.get("URLs", {}),
        music=tables["MusicData"],
        groups=tables.get("GroupData", {}),
        albums=tables.get("AlbumData", {}),
        group_labels=group_names(game, tables, strings or {}),
        languages=game.languages,
        strings=strings or {},
    )


type NameKind = Literal["song", "deck"]
HIDDEN_SUFFIX = " (Hidden)"


def deck_names(index: Index, deck: Deck) -> set[str]:
    """Every name a deck goes by, folded for comparison."""
    entry = index.locale.get(str(deck.raw.get("localeName")), {})
    names = {name_key(deck.name), name_key(deck.label)}
    names |= {
        name_key(clean(entry.get(lang))) for lang in LOCALE_COLUMNS if entry.get(lang)
    }
    names.discard("")
    return names


def loose_key(name: str) -> str:
    """Name folded further: punctuation and spacing dropped ("M & D" == "M&D")."""
    return re.sub(r"[\W_]+", "", name_key(name))


def find_deck_by_name(
    index: Index, name: str, aliases: Mapping[str, str] | None = None
) -> Deck | None:
    """The deck a name from the old sheets stood for.

    Matches the English, Korean and Japanese names, ignoring punctuation and
    spacing. ``aliases`` maps a name the sheets used to what the deck is called
    now (decks get renamed). v0 called a deck that only holds hidden songs
    "<name> (Hidden)"; that finds the hidden-only deck of the name, or failing
    that the deck itself.
    """
    decks = list(index.decks)
    names = {d.code: deck_names(index, d) for d in decks}
    loose = {code: {loose_key(n) for n in each} for code, each in names.items()}
    renamed = {name_key(old): new for old, new in (aliases or {}).items()}

    def lookup(text: str) -> list[Deck]:
        for wanted in (text, renamed.get(name_key(text), text)):
            exact = [d for d in decks if name_key(wanted) in names[d.code]]
            if exact:
                return exact
            key = loose_key(wanted)
            fuzzy = [d for d in decks if key and key in loose[d.code]]
            if fuzzy:
                return fuzzy
        return []

    text, hidden = name.strip(), False
    found = lookup(text)
    if not found and text.casefold().endswith(HIDDEN_SUFFIX.casefold()):
        text, hidden = text[: -len(HIDDEN_SUFFIX)].rstrip(), True
        found = lookup(text)
    if not found:
        return None
    if hidden:
        return next((d for d in found if not d.is_main), found[0])
    return next((d for d in found if d.is_main), found[0])


class Indexes:
    """Per-game indexes, rebuilt lazily when a game's tables change."""

    def __init__(
        self,
        service: DataService,
        *,
        rules: BonusRules = DEFAULT_RULES,
        clock: Callable[[Game], datetime] = lambda game: game.now(),
    ) -> None:
        self._service = service
        self._rules = rules
        self._clock = clock
        self._names: dict[str, dict[tuple[NameKind, int], str]] = {}
        self._indexes: dict[str, tuple[tuple[object, ...] | None, Index | None]] = {}
        self._warming: dict[str, asyncio.Lock] = {}
        self._calendars: dict[
            str, tuple[tuple[object, ...] | None, tuple[int, ...], BonusCalendar]
        ] = {}

    def today(self, game: Game) -> date:
        return self._clock(game).date()

    def set_names(self, key: str, names: Mapping[tuple[NameKind, int], str]) -> None:
        """Replace the display names of a game; its index is rebuilt on next use."""
        self._names[key] = dict(names)

    def _source(self, key: str, data: State) -> tuple[object, ...] | None:
        """The table objects an index is built from.

        A sync makes a new ``LoadedTables`` every hour but keeps the table
        objects that did not change, so identity of the tables themselves is
        what says whether anything needs rebuilding.
        """
        if data.loaded_tables is None:
            return None
        return (
            *(data.tables.get(name) for name in SOURCE_TABLES),
            data.strings,
            self._names.get(key),
        )

    @staticmethod
    def _same(a: tuple[object, ...] | None, b: tuple[object, ...] | None) -> bool:
        if a is None or b is None:
            return a is b
        return len(a) == len(b) and all(x is y for x, y in zip(a, b))

    def _build(
        self, key: str, data: State, source: tuple[object, ...] | None
    ) -> Index | None:
        if source is None:
            return None
        return build_index(data.game, data.tables, data.strings, self._names.get(key))

    def get(self, key: str) -> Index | None:
        data = self._service.get(key)
        source = self._source(key, data)
        cached = self._indexes.get(key)
        if cached and self._same(cached[0], source):
            return cached[1]
        index = self._build(key, data, source)
        self._indexes[key] = (source, index)
        return index

    @staticmethod
    def _years(year: int) -> tuple[int, ...]:
        return tuple(
            range(year - CALENDAR_YEARS_BEFORE, year + CALENDAR_YEARS_AFTER + 1)
        )

    def _cached_calendar(
        self, key: str, source: tuple[object, ...] | None, years: tuple[int, ...]
    ) -> BonusCalendar | None:
        cached = self._calendars.get(key)
        if cached and self._same(cached[0], source) and cached[1] == years:
            return cached[2]
        return None

    def _build_calendar(self, index: Index, years: tuple[int, ...]) -> BonusCalendar:
        songs = build_song_periods(
            index.decks,
            index.artists,
            index.locale,
            years,
            self._rules,
            index.languages,
        )
        return BonusCalendar.build(songs, years)

    def calendar(self, key: str, year: int) -> BonusCalendar | None:
        """The bonus calendar covering ``year`` and the one after it.

        Built here on the spot if it is not ready; that holds the event loop for
        seconds, so code that can wait calls :meth:`warm` first.
        """
        index = self.get(key)
        if index is None or not index.game.has_bonuses:
            return None
        years = self._years(year)
        source = self._source(key, self._service.get(key))
        if (calendar := self._cached_calendar(key, source, years)) is not None:
            return calendar
        calendar = self._build_calendar(index, years)
        self._calendars[key] = (source, years, calendar)
        return calendar

    async def warm(self, key: str, year: int | None = None) -> None:
        """Build a game's index and calendar in a thread, if they are out of date.

        Both are big (a game's songs over several years) and are rebuilt after
        every change to its tables. Done on the event loop they stalled it for
        seconds, long enough to miss a lease renewal; done here, :meth:`get` and
        :meth:`calendar` then find them ready.
        """
        async with self._warming.setdefault(key, asyncio.Lock()):
            data = self._service.get(key)
            source = self._source(key, data)
            cached = self._indexes.get(key)
            if cached and self._same(cached[0], source):
                index = cached[1]
            else:
                index = await asyncio.to_thread(self._build, key, data, source)
                self._indexes[key] = (source, index)
            if index is None or not index.game.has_bonuses:
                return
            years = self._years(
                year if year is not None else self.today(index.game).year
            )
            if self._cached_calendar(key, source, years) is not None:
                return
            calendar = await asyncio.to_thread(self._build_calendar, index, years)
            self._calendars[key] = (source, years, calendar)

    def current_calendar(self, key: str) -> BonusCalendar | None:
        index = self.get(key)
        if index is None:
            return None
        return self.calendar(key, self.today(index.game).year)
