"""What a bonus ping says: the day's calendar events, grouped per deck.

Pure planning only. The task decides who gets pinged and when; this module
decides what there is to say about a deck on a given day.

A deck has two kinds of entry, as the game's own list shows them:

* a member birthday, which is one entry for the whole deck, and
* a song that has a release anniversary, which is an entry of its own.

Each entry is announced when it starts and when it ends.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal, NamedTuple

from games.bonus.events import BonusEvent, EventKind
from games.bonus.periods import Bonus, MemberBonus, has_release, members_of
from games.data.decks import Deck

type Category = Literal["start", "end"]
# What a ping says an entry does: "drop" is a following bonus that gives less,
# so the higher one ends as it begins (a ping of the "end" kind).
type Section = Literal["start", "drop", "end"]


@dataclass(frozen=True, slots=True)
class NoticeLine:
    """One entry of a ping: a bonus that begins or is on its last day, the songs and
    the total percentage. ``drop`` is true when it replaces a higher one.
    """

    category: Category  # "start": an entry begins; "end": it is on its last day
    song_codes: tuple[int, ...]
    all_songs: bool
    bonuses: tuple[Bonus, ...]
    total: int  # the percentage of the entry
    start: date  # the entry's own window
    end: date
    day: date  # the day the line is about
    before: int | None = None  # the percentage this replaces, when it differs

    @property
    def drop(self) -> bool:
        return self.before is not None and self.total < self.before

    @property
    def section(self) -> Section:
        return "drop" if self.drop else self.category

    @property
    def has_release(self) -> bool:
        return has_release(self.bonuses)

    @property
    def members(self) -> tuple[MemberBonus, ...]:
        return members_of(self.bonuses)


class _Key(NamedTuple):
    category: Category
    bonuses: tuple[Bonus, ...]
    total: int
    start: date
    end: date
    day: date
    before: int | None
    song: int | None  # set for an anniversary entry, which is never merged


def category_of(event: BonusEvent) -> Category:
    """A new entry starts and the last day ends.

    An entry that follows another counts as starting when it gives more and as
    the other ending when it gives less.
    """
    return "end" if event.kind is EventKind.END or event.is_drop else "start"


def deck_notices(
    deck: Deck, events: Iterable[BonusEvent]
) -> dict[Category, list[NoticeLine]]:
    """Group a deck's events for one day into lines.

    Birthday events that are alike across songs are one line ("All Songs");
    an anniversary entry is a line for its song.
    """
    visible = {s.code for s in deck.visible_songs}
    groups: dict[_Key, list[BonusEvent]] = defaultdict(list)
    for event in events:
        if event.deck_code != deck.code or event.song_code not in visible:
            continue
        period = event.period
        anniversary = has_release(period.bonuses)
        key = _Key(
            category_of(event),
            period.bonuses,
            period.total,
            period.start,
            period.end,
            event.day,
            event.change_from,
            event.song_code if anniversary else None,
        )
        groups[key].append(event)

    lines: dict[Category, list[NoticeLine]] = {"start": [], "end": []}
    for key, evs in groups.items():
        codes = tuple(sorted(e.song_code for e in evs))
        lines[key.category].append(
            NoticeLine(
                category=key.category,
                song_codes=codes,
                all_songs=set(codes) == visible,
                bonuses=key.bonuses,
                total=key.total,
                start=key.start,
                end=key.end,
                day=key.day,
                before=key.before,
            )
        )
    for group in lines.values():
        group.sort(key=lambda line: (line.end, line.start, line.song_codes))
    return lines


def notices_for_day(
    decks: Mapping[int, Deck], events: Iterable[BonusEvent], deck_codes: Iterable[int]
) -> dict[int, dict[Category, list[NoticeLine]]]:
    """Per wanted deck, the lines for a day's events; decks with none are left out."""
    wanted = set(deck_codes)
    by_deck: dict[int, list[BonusEvent]] = defaultdict(list)
    for event in events:
        if event.deck_code in wanted:
            by_deck[event.deck_code].append(event)
    result: dict[int, dict[Category, list[NoticeLine]]] = {}
    for code, evs in by_deck.items():
        deck = decks.get(code)
        if deck is None:
            continue
        lines = deck_notices(deck, evs)
        if lines["start"] or lines["end"]:
            result[code] = lines
    return result


def hours_due(local_hour: int, offset: int, days_ahead: int = 1) -> bool:
    """Whether a ping set for ``offset`` hours before a day is due.

    ``days_ahead`` is how far that day is from today (1 is tomorrow). A ping is
    due from its hour until the day begins, so one missed by a restart, or one
    whose hour had passed when the setting was changed, is still sent; the
    delivery log keeps it to once. An offset of 0 is off.
    """
    return offset > 0 and offset >= days_ahead * 24 - local_hour
