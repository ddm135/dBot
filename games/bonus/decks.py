"""Decks (a group's songs and members) as the game tables describe them, and their score ceilings."""

import json
import re
from collections import defaultdict
from collections.abc import Collection, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from zoneinfo import ZoneInfo

from games.bonus.schedule import ms_to_date
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


@dataclass(frozen=True, slots=True)
class Song:
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


@dataclass(frozen=True, slots=True)
class Deck:
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
    decks: Mapping[int, Deck]
    songs: Mapping[int, Song]
    timezone: ZoneInfo
    _deck_order: tuple[int, ...] = ()

    def __iter__(self) -> Iterator[Deck]:
        return (self.decks[c] for c in self._deck_order)

    def deck_of(self, song_code: int) -> Deck | None:
        song = self.songs.get(song_code)
        return self.decks.get(song.deck_code) if song else None


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
    album code, when given, else from the songs' ``albumName``); songs of no known album stay in their
    group's deck. ``group_names`` (by group code) overrides the groups' locale names,
    and ``song_names`` (by song code) the songs'.
    """
    music = tables.get("MusicData", {})
    groups = tables.get("GroupData", {})
    locale = tables.get("LocaleData", {})
    albums = tables.get("AlbumData", {}) if album_decks else {}
    titles = album_titles or {}
    given = group_names or {}
    given_songs = song_names or {}

    def group_name(code: str) -> str | None:
        """A group's name: the one given, else its locale text."""
        group = groups.get(code)
        return given.get(code) or (
            entry_name(locale, group, languages) if group else None
        )

    songs_by_deck: dict[str, list[Entry]] = defaultdict(list)
    for song in music.values():
        album = str(song.get("albumCode"))
        key = album if album in albums else str(song["groupData"])
        songs_by_deck[key].append(song)

    known = dict.fromkeys((*albums, *groups))
    deck_codes = [c for c in known if include_empty or c in songs_by_deck]
    deck_codes += sorted(set(songs_by_deck) - set(known), key=int)  # missing decks

    def album_title(code: str) -> str | None:
        songs = songs_by_deck.get(code)
        if not songs:
            return None
        first = min(songs, key=lambda m: (_order(m.get("orderIndex")), _code(m)))
        artist = group_name(str(albums[code].get("groupCode"))) or locale_text(
            locale, first.get("localeDisplayGroupName"), None, languages
        )
        album = titles.get(code) or locale_text(
            locale, first.get("albumName"), None, languages
        )
        return " : ".join(part for part in (artist, album) if part) or None

    def deck_name(code: str) -> str:
        if shown := (deck_overrides or {}).get(code):
            return shown
        if code in albums:
            return album_title(code) or f"Deck {code}"
        return group_name(code) or f"Deck {code}"

    names = {c: deck_name(c) for c in deck_codes}
    by_name: dict[str, list[str]] = defaultdict(list)
    for code, name in names.items():
        by_name[name_key(name)].append(code)

    is_main = {
        c: any(not m.get("isHidden") for m in songs_by_deck.get(c, []))
        for c in deck_codes
    }

    def sort_key(code: str) -> tuple[int, int, int, int, int]:
        """Groups in order, each followed by its albums."""
        group_code = str(albums[code].get("groupCode")) if code in albums else code
        g = groups.get(group_code, {})
        return (
            _order(g.get("secondOrderIndex")),
            _order(g.get("orderIndex")),
            int(group_code) if group_code.isdigit() else _LAST,
            code in albums,
            int(code),
        )

    decks: dict[int, Deck] = {}
    songs: dict[int, Song] = {}
    order: list[int] = []

    for dc in sorted(deck_codes, key=sort_key):
        album_entry = albums.get(dc)
        group = groups.get(dc, {})
        name = names[dc]
        same = [c for c in by_name[name_key(name)] if c != dc]
        mains = [c for c in by_name[name_key(name)] if is_main[c]]
        plain = not same or (is_main[dc] and len(mains) == 1)
        label = name if plain else f"{name} [{dc}]"

        entries = sorted(
            songs_by_deck.get(dc, []),
            key=lambda m: (_order(m.get("orderIndex")), _code(m)),
        )
        titles_in_deck = {
            _code(m): (
                given_songs.get(str(_code(m)))
                or entry_name(locale, m, languages)
                or f"Song {_code(m)}"
            )
            for m in entries
        }
        in_deck: dict[str, list[int]] = defaultdict(list)
        for song_code, song_name in titles_in_deck.items():
            in_deck[name_key(song_name)].append(song_code)

        deck_songs: list[Song] = []
        for m in entries:
            scode = _code(m)
            sname = titles_in_deck[scode]
            same_songs = tuple(c for c in in_deck[name_key(sname)] if c != scode)
            display = locale_text(
                locale, m.get("localeDisplayGroupName"), None, languages
            )
            deck_songs.append(
                Song(
                    code=scode,
                    name=sname,
                    label=f"{sname} [{scode}]" if same_songs else sname,
                    deck_code=int(dc),
                    is_hidden=bool(m.get("isHidden")),
                    release=ms_to_date((album_entry or m).get("releaseDate"), timezone),
                    album=titles.get(dc)
                    or locale_text(locale, m.get("albumName"), None, languages),
                    track_number=m.get("trackNumber"),
                    display_group=display if display != name else None,
                    analytics_name=m.get("analyticsData"),
                    same_name_codes=same_songs,
                    artist_codes=_parse_codes(m.get("artistCode")),
                    raw=m,
                )
            )
        for s in deck_songs:
            songs[s.code] = s

        decks[int(dc)] = Deck(
            code=int(dc),
            name=name,
            label=label,
            is_main=is_main[dc],
            in_group_data=dc in groups,
            same_name_codes=tuple(int(c) for c in same),
            songs=tuple(deck_songs),
            group_type=group.get("groupType"),
            integrate_code=group.get("integrateCode"),
            analytics_name=group.get("analyticsData"),
            raw=album_entry or group,
        )
        order.append(int(dc))

    return DeckIndex(
        MappingProxyType(decks), MappingProxyType(songs), timezone, tuple(order)
    )


PER_MEMBER = 15_000
BASE_MEMBERS = 3
EXCLUDED_ARTIST_TYPE = 4


@dataclass(frozen=True, slots=True)
class DeckScore:
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
