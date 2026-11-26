"""Searching decks and songs by name, in any language, plus aliases."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from db.misc import Aliases, AliasKind
from games.bonus.decks import Deck, Song, clean, name_key
from games.data.schema import LOCALE_COLUMNS
from games.index import HIDDEN_SUFFIX, Index, Indexes
from games.models import Entry

MAX_RESULTS = 25  # Discord's autocomplete limit
MAX_CHOICE_LENGTH = 100


@dataclass(frozen=True, slots=True)
class Hit:
    """One search result: a deck or song, its label, and whether it is hidden."""

    code: int
    label: str
    deck_code: int | None = None  # for songs
    hidden: bool = False

    @property
    def choice_name(self) -> str:
        """The label as an autocomplete choice: marked if hidden, cut to Discord's length."""
        name = f"{self.label}{HIDDEN_SUFFIX}" if self.hidden else self.label
        return (
            name
            if len(name) <= MAX_CHOICE_LENGTH
            else name[: MAX_CHOICE_LENGTH - 1] + "…"
        )


@dataclass(frozen=True, slots=True)
class _Entry:
    hit: Hit
    terms: tuple[str, ...]


def rank(terms: Iterable[str], query: str) -> int | None:
    """0 exact, 1 prefix, 2 word prefix, 3 substring; None if no match."""
    best: int | None = None
    for term in terms:
        if term == query:
            return 0
        if term.startswith(query):
            found = 1
        elif f" {query}" in term:
            found = 2
        elif query in term:
            found = 3
        else:
            continue
        best = found if best is None else min(best, found)
    return best


def _locale_terms(locale: Mapping[str, Entry], code: object) -> list[str]:
    entry = locale.get(str(code)) if code is not None else None
    if not entry:
        return []
    return [t for lang in LOCALE_COLUMNS if (t := clean(entry.get(lang)))]


def _terms(
    label: str, locale_terms: list[str], extra: Iterable[object], aliases: list[str]
) -> tuple[str, ...]:
    raw = [label, *locale_terms, *(e for e in extra if isinstance(e, str)), *aliases]
    return tuple(dict.fromkeys(k for t in raw if (k := name_key(t))))


class Search:
    """Searching one game's decks and songs by name, any language, and by alias."""

    def __init__(
        self, index: Index, aliases: Mapping[tuple[AliasKind, int], list[str]]
    ) -> None:
        self._decks: list[_Entry] = []
        self._songs: list[_Entry] = []
        for deck in index.decks:
            self._decks.append(_deck_entry(index, deck, aliases))
            for song in deck.songs:
                self._songs.append(_song_entry(index, song, aliases))

    def decks(self, query: str, limit: int = MAX_RESULTS) -> list[Hit]:
        """The decks matching ``query``, best first."""
        return _search(self._decks, query, limit)

    def songs(
        self, query: str, deck_code: int | None = None, limit: int = MAX_RESULTS
    ) -> list[Hit]:
        pool = (
            self._songs
            if deck_code is None
            else [e for e in self._songs if e.hit.deck_code == deck_code]
        )
        return _search(pool, query, limit)


def _deck_entry(
    index: Index, deck: Deck, aliases: Mapping[tuple[AliasKind, int], list[str]]
) -> _Entry:
    config = index.game.strings
    names = []
    if config:  # the string tables hold every language, not just the shown one
        key = config.album_key if str(deck.code) in index.albums else config.group_key
        names = index.string_names(key, deck.code)
    terms = _terms(
        deck.label,
        _locale_terms(index.locale, deck.raw.get("localeName")) + names,
        [deck.analytics_name],
        aliases.get(("deck", deck.code), []),
    )
    return _Entry(Hit(deck.code, deck.label, hidden=not deck.is_main), terms)


def _song_entry(
    index: Index, song: Song, aliases: Mapping[tuple[AliasKind, int], list[str]]
) -> _Entry:
    config = index.game.strings
    names = index.string_names(config.song_key, song.code) if config else []
    terms = _terms(
        song.label,
        _locale_terms(index.locale, song.raw.get("localeName")) + names,
        [song.analytics_name, str(song.code)],
        aliases.get(("song", song.code), []),
    )
    return _Entry(Hit(song.code, song.label, song.deck_code, song.is_hidden), terms)


def _search(entries: list[_Entry], query: str, limit: int) -> list[Hit]:
    query = name_key(query)
    if not query:
        return [e.hit for e in entries[:limit]]
    ranked = []
    for position, entry in enumerate(entries):
        r = rank(entry.terms, query)
        if r is not None:
            ranked.append((r, position, entry.hit))
    ranked.sort(key=lambda item: item[:2])
    return [hit for _, _, hit in ranked[:limit]]


class Searcher:
    """Search for every game, rebuilt when tables or aliases change."""

    def __init__(self, indexes: Indexes, aliases: Aliases) -> None:
        self._indexes = indexes
        self._store = aliases
        self._aliases: dict[str, dict[tuple[AliasKind, int], list[str]]] = {}
        self._built: dict[str, tuple[Index, Search]] = {}

    async def load(self, game_keys: Iterable[str]) -> None:
        for key in game_keys:
            self._aliases[key] = await self._store.all(key)
        self._built.clear()

    def game(self, key: str) -> Search | None:
        index = self._indexes.get(key)
        if index is None:
            return None
        built = self._built.get(key)
        if built and built[0] is index:
            return built[1]
        search = Search(index, self._aliases.get(key, {}))
        self._built[key] = (index, search)
        return search

    async def add_alias(
        self, game: str, kind: AliasKind, code: int, alias: str
    ) -> bool:
        added = await self._store.add(game, kind, code, alias)
        if added:
            self._aliases.setdefault(game, {}).setdefault((kind, code), []).append(
                alias.strip().casefold()
            )
            self._built.pop(game, None)
        return added

    async def remove_alias(
        self, game: str, kind: AliasKind, code: int, alias: str
    ) -> bool:
        removed = await self._store.remove(game, kind, code, alias)
        if removed:
            items = self._aliases.get(game, {}).get((kind, code), [])
            if alias.strip().casefold() in items:
                items.remove(alias.strip().casefold())
            self._built.pop(game, None)
        return removed

    def aliases_of(self, game: str, kind: AliasKind, code: int) -> list[str]:
        return list(self._aliases.get(game, {}).get((kind, code), []))
