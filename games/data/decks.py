"""Decks (a group's songs and members) as the game tables describe them, and their score ceilings."""

import json
import re
from collections import defaultdict
from collections.abc import Collection, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from zoneinfo import ZoneInfo

from games.data.schedule import ms_to_date
from games.models import Entry, Tables

_TAG = re.compile(r"<[^>]+>")
_LAST = 10**9


def clean(text: str | None) -> str | None:
    """Strip rich-text tags such as ``<size=20>``."""
    return _TAG.sub("", text).strip() if isinstance(text, str) else None


_FOLD = str.maketrans({"æ": "ae", "Æ": "ae", "œ": "oe", "Œ": "oe"})


def name_key(name: str | None) -> str:
    """Comparison key for "same name": case, whitespace and ligature insensitive
    (``æspa`` and ``aespa`` are the same name)."""
    return " ".join((name or "").translate(_FOLD).casefold().split())


DEFAULT_LANGUAGES = ("enUS", "koKR")


def locale_text(
    locale: Mapping[str, Entry],
    code: object,
    fallback: str | None = None,
    languages: Sequence[str] = DEFAULT_LANGUAGES,
) -> str | None:
    """Resolve a locale code to the first of ``languages`` it has, else ``fallback``."""
    entry = locale.get(str(code)) if code is not None else None
    text = next((entry[lang] for lang in languages if entry and entry.get(lang)), None)
    return clean(text or fallback)


def entry_name(
    locale: Mapping[str, Entry],
    entry: Entry,
    languages: Sequence[str] = DEFAULT_LANGUAGES,
) -> str | None:
    """The name of a group, artist or song: its locale text, else ``analyticsData``."""
    fallback = entry.get("analyticsData")
    return locale_text(
        locale,
        entry.get("localeName"),
        fallback if isinstance(fallback, str) else None,
        languages,
    )


def _order(value: object) -> int:
    return value if isinstance(value, int) else _LAST


def _code(entry: Entry) -> int:
    return int(entry["code"])


HIDDEN_SUFFIX = " (Hidden)"


@dataclass(frozen=True, slots=True)
class Song:
    """A song of a deck, with the fields of the game table it comes from (``raw``)."""

    code: int
    name: str
    label: str  # unique inside its deck
    deck_code: int
    is_hidden: bool
    release: date | None
    album: str | None
    track_number: int | None
    display_group: str | None
    analytics_name: str | None
    same_name_codes: tuple[int, ...] = ()
    artist_codes: tuple[int, ...] = ()
    raw: Entry = field(default_factory=dict, repr=False, compare=False)

    @property
    def has_duplicate_name(self) -> bool:
        return bool(self.same_name_codes)

    @property
    def display_label(self) -> str:
        """The label, marked ``(Hidden)`` for a hidden song, as shown to users."""
        return f"{self.label}{HIDDEN_SUFFIX}" if self.is_hidden else self.label


@dataclass(frozen=True, slots=True)
class Deck:
    """A deck: an artist or an album with songs. ``label`` tells apart decks with
    the same name; ``is_main`` is false for a deck with no visible song.
    """

    code: int
    name: str
    label: str  # unique among decks
    is_main: bool  # holds at least one visible song
    in_group_data: bool
    same_name_codes: tuple[int, ...]
    songs: tuple[Song, ...]
    group_type: int | None = None
    integrate_code: int | None = None
    analytics_name: str | None = None
    raw: Entry = field(default_factory=dict, repr=False, compare=False)

    @property
    def has_duplicate_name(self) -> bool:
        return bool(self.same_name_codes)

    @property
    def display_name(self) -> str:
        """The name, marked ``(Hidden)`` for a deck with no visible song."""
        return self.name if self.is_main else f"{self.name}{HIDDEN_SUFFIX}"

    @property
    def visible_songs(self) -> tuple[Song, ...]:
        return tuple(s for s in self.songs if not s.is_hidden)


def _parse_codes(value: object) -> tuple[int, ...]:
    """``artistCode`` is a JSON-encoded list, or already a list."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return ()
    if not isinstance(value, list):
        return ()
    codes: list[int] = []
    for item in value:
        try:
            codes.append(int(item))
        except TypeError, ValueError:
            continue
    return tuple(dict.fromkeys(codes))


@dataclass(frozen=True, slots=True, eq=False)
class DeckIndex:
    """Every deck and song of a game by code, with the game's timezone."""

    decks: Mapping[int, Deck]
    songs: Mapping[int, Song]
    timezone: ZoneInfo
    _deck_order: tuple[int, ...] = ()

    def __iter__(self) -> Iterator[Deck]:
        return (self.decks[c] for c in self._deck_order)

    def deck_of(self, song_code: int) -> Deck | None:
        song = self.songs.get(song_code)
        return self.decks.get(song.deck_code) if song else None


class _Builder:
    """The steps of :func:`build_deck_index`, one method each.

    Deck and song codes are strings while they are looked up in the tables
    (that is how the tables key them) and ints in the result.
    """

    def __init__(
        self,
        tables: Tables,
        timezone: ZoneInfo,
        *,
        album_decks: bool,
        album_titles: Mapping[str, str] | None,
        group_names: Mapping[str, str] | None,
        song_names: Mapping[str, str] | None,
        languages: Sequence[str],
        deck_overrides: Mapping[str, str] | None,
    ) -> None:
        self.timezone = timezone
        self.languages = languages
        self.music = tables.get("MusicData", {})
        self.groups = tables.get("GroupData", {})
        self.locale = tables.get("LocaleData", {})
        # Only games with album decks read the album table at all.
        self.albums = tables.get("AlbumData", {}) if album_decks else {}
        self.album_titles = album_titles or {}
        self.group_names = group_names or {}
        self.song_names = song_names or {}
        self.deck_overrides = deck_overrides or {}
        self.songs_by_deck = self._songs_by_deck()

    def _songs_by_deck(self) -> dict[str, list[Entry]]:
        """Each song under its album when that album is a deck, else its group."""
        result: dict[str, list[Entry]] = defaultdict(list)
        for song in self.music.values():
            album = str(song.get("albumCode"))
            key = album if album in self.albums else str(song["groupData"])
            result[key].append(song)
        return result

    # -- names ------------------------------------------------------------

    def group_name(self, code: str) -> str | None:
        """A group's name: the one given, else its locale text."""
        group = self.groups.get(code)
        return self.group_names.get(code) or (
            entry_name(self.locale, group, self.languages) if group else None
        )

    def album_title(self, code: str) -> str | None:
        """``<artist> : <album>``, taken from the album's first song."""
        songs = self.songs_by_deck.get(code)
        if not songs:
            return None
        first = min(songs, key=lambda m: (_order(m.get("orderIndex")), _code(m)))
        artist = self.group_name(
            str(self.albums[code].get("groupCode"))
        ) or locale_text(
            self.locale, first.get("localeDisplayGroupName"), None, self.languages
        )
        album = self.album_titles.get(code) or locale_text(
            self.locale, first.get("albumName"), None, self.languages
        )
        return " : ".join(part for part in (artist, album) if part) or None

    def deck_name(self, code: str) -> str:
        if shown := self.deck_overrides.get(code):
            return shown
        if code in self.albums:
            return self.album_title(code) or f"Deck {code}"
        return self.group_name(code) or f"Deck {code}"

    # -- order ------------------------------------------------------------

    def deck_codes(self, include_empty: bool) -> list[str]:
        """Every deck to build: the albums and groups, then decks only the songs name."""
        known = dict.fromkeys((*self.albums, *self.groups))  # keeps their order
        codes = [c for c in known if include_empty or c in self.songs_by_deck]
        # A song can point at a group the table does not have.
        codes += sorted(set(self.songs_by_deck) - set(known), key=int)
        return codes

    def sort_key(self, code: str) -> tuple[int, int, int, int, int]:
        """Groups in order, each followed by its albums."""
        in_albums = code in self.albums
        group_code = str(self.albums[code].get("groupCode")) if in_albums else code
        g = self.groups.get(group_code, {})
        return (
            _order(g.get("secondOrderIndex")),
            _order(g.get("orderIndex")),
            int(group_code) if group_code.isdigit() else _LAST,
            in_albums,
            int(code),
        )

    # -- decks and songs --------------------------------------------------

    def build(self, include_empty: bool) -> DeckIndex:
        codes = self.deck_codes(include_empty)
        names = {c: self.deck_name(c) for c in codes}
        by_name: dict[str, list[str]] = defaultdict(list)
        for code, name in names.items():
            by_name[name_key(name)].append(code)
        # A deck with only hidden songs does not count as "the" deck of a name.
        is_main = {
            c: any(not m.get("isHidden") for m in self.songs_by_deck.get(c, []))
            for c in codes
        }

        decks: dict[int, Deck] = {}
        songs: dict[int, Song] = {}
        order: list[int] = []
        for code in sorted(codes, key=self.sort_key):
            name = names[code]
            same = [c for c in by_name[name_key(name)] if c != code]
            mains = [c for c in by_name[name_key(name)] if is_main[c]]
            # Same-named decks get "[code]" added, except the one real deck.
            plain = not same or (is_main[code] and len(mains) == 1)
            deck_songs = self.songs_of(code, name)
            group = self.groups.get(code, {})
            album_entry = self.albums.get(code)
            decks[int(code)] = Deck(
                code=int(code),
                name=name,
                label=name if plain else f"{name} [{code}]",
                is_main=is_main[code],
                in_group_data=code in self.groups,
                same_name_codes=tuple(int(c) for c in same),
                songs=tuple(deck_songs),
                group_type=group.get("groupType"),
                integrate_code=group.get("integrateCode"),
                analytics_name=group.get("analyticsData"),
                raw=album_entry or group,
            )
            songs.update((s.code, s) for s in deck_songs)
            order.append(int(code))
        return DeckIndex(
            MappingProxyType(decks),
            MappingProxyType(songs),
            self.timezone,
            tuple(order),
        )

    def songs_of(self, code: str, deck_name: str) -> list[Song]:
        """A deck's songs in order. Songs with the same name inside one deck get
        ``[code]`` added to their label."""
        entries = sorted(
            self.songs_by_deck.get(code, []),
            key=lambda m: (_order(m.get("orderIndex")), _code(m)),
        )
        names = {
            _code(m): (
                self.song_names.get(str(_code(m)))
                or entry_name(self.locale, m, self.languages)
                or f"Song {_code(m)}"
            )
            for m in entries
        }
        with_name: dict[str, list[int]] = defaultdict(list)
        for song_code, song_name in names.items():
            with_name[name_key(song_name)].append(song_code)

        album_entry = self.albums.get(code)
        result: list[Song] = []
        for m in entries:
            song_code = _code(m)
            name = names[song_code]
            same = tuple(c for c in with_name[name_key(name)] if c != song_code)
            display = locale_text(
                self.locale, m.get("localeDisplayGroupName"), None, self.languages
            )
            result.append(
                Song(
                    code=song_code,
                    name=name,
                    label=f"{name} [{song_code}]" if same else name,
                    deck_code=int(code),
                    is_hidden=bool(m.get("isHidden")),
                    # An album deck has one release date: the album's.
                    release=ms_to_date(
                        (album_entry or m).get("releaseDate"), self.timezone
                    ),
                    album=self.album_titles.get(code)
                    or locale_text(
                        self.locale, m.get("albumName"), None, self.languages
                    ),
                    track_number=m.get("trackNumber"),
                    display_group=display if display != deck_name else None,
                    analytics_name=m.get("analyticsData"),
                    same_name_codes=same,
                    artist_codes=_parse_codes(m.get("artistCode")),
                    raw=m,
                )
            )
        return result


def build_deck_index(
    tables: Tables,
    timezone: ZoneInfo,
    *,
    include_empty: bool = False,
    album_decks: bool = False,
    album_titles: Mapping[str, str] | None = None,
    group_names: Mapping[str, str] | None = None,
    song_names: Mapping[str, str] | None = None,
    languages: Sequence[str] = DEFAULT_LANGUAGES,
    deck_overrides: Mapping[str, str] | None = None,
) -> DeckIndex:
    """Build the index. Missing tables give an empty index.

    A deck is a group (an artist). In a game with ``album_decks`` each album of
    ``AlbumData`` is a deck of its own, named "<artist> : <album>", and takes
    its release date from the album (and its title from ``album_titles``, by
    album code, when given, else from the songs' ``albumName``); songs of no
    known album stay in their group's deck. ``group_names`` (by group code)
    overrides the groups' locale names, and ``song_names`` (by song code) the
    songs'.
    """
    return _Builder(
        tables,
        timezone,
        album_decks=album_decks,
        album_titles=album_titles,
        group_names=group_names,
        song_names=song_names,
        languages=languages,
        deck_overrides=deck_overrides,
    ).build(include_empty)


PER_MEMBER = 15_000
BASE_MEMBERS = 3
EXCLUDED_ARTIST_TYPE = 4


@dataclass(frozen=True, slots=True)
class DeckScore:
    """What a deck's best score depends on: its member count and the game's base score."""

    member_count: int
    base: int  # 0 when the game has no known base score


def member_counts(artists: Mapping[str, Entry]) -> dict[int, int]:
    """Members per deck: artists of the deck that are not of type 4."""
    counts: dict[int, int] = {}
    for artist in artists.values():
        if artist.get("artistType", 1) == EXCLUDED_ARTIST_TYPE:
            continue
        try:
            group = int(artist["group"])
        except KeyError, TypeError, ValueError:
            continue
        counts[group] = counts.get(group, 0) + 1
    return counts


def deck_scores(
    tables: Tables, base_score: int | None, deck_codes: list[int]
) -> dict[int, DeckScore]:
    """The :class:`DeckScore` of every deck."""
    counts = member_counts(tables.get("ArtistData", {}))
    scores: dict[int, DeckScore] = {}
    for code in deck_codes:
        members = counts.get(code, 0)
        base = base_score + PER_MEMBER * (members - BASE_MEMBERS) if base_score else 0
        scores[code] = DeckScore(members, base)
    return scores


def live_theme_maximum(
    tables: Tables, counts: Mapping[int, int], deck_codes: Collection[int]
) -> int:
    """The most live-theme score a player can have, or 0 if the game has none.

    Only games whose ``LiveThemeData`` has ``collectRewardID`` count it, and
    only themes of the given decks add to it.
    """
    themes = tables.get("LiveThemeData", {})
    if not themes or "collectRewardID" not in next(iter(themes.values())):
        return 0
    total = 0
    for theme in themes.values():
        try:
            group = int(theme["groupID"])
        except KeyError, TypeError, ValueError:
            continue
        if group not in deck_codes:
            continue
        total += PER_MEMBER * counts.get(group, 0)
    return total
