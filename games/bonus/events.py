"""What changes on which day: the events of a song's periods, and the calendar of them."""

from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from games.bonus.periods import (
    ONE_DAY,
    Bonus,
    Period,
    ReleaseBonus,
    SongPeriods,
)
from games.data.decks import (
    Song,
)


class EventKind(StrEnum):
    """What happens on a day: a bonus starts, the active set changes, or the last day ends."""

    START = "start"  # a bonus begins on a song that had none
    CHANGE = "change"  # the active set or the total changes
    END = "end"  # the last active day; the bonus ends after it


@dataclass(frozen=True, slots=True)
class BonusEvent:
    """Something that changes on a day for a song: a bonus starts, changes (the
    period before is ``before``) or ends. The properties give the percentages
    before and after and the bonuses added and removed.
    """

    day: date
    kind: EventKind
    song_code: int
    deck_code: int
    period: Period  # the period this event belongs to
    before: Period | None = None  # the previous period, for a change

    @property
    def from_percent(self) -> int:
        match self.kind:
            case EventKind.START:
                return 0
            case EventKind.CHANGE:
                return self.before.total if self.before else 0
            case EventKind.END:
                return self.period.total

    @property
    def to_percent(self) -> int:
        return 0 if self.kind is EventKind.END else self.period.total

    @property
    def added(self) -> tuple[Bonus, ...]:
        match self.kind:
            case EventKind.START:
                return self.period.bonuses
            case EventKind.CHANGE:
                old = set(self.before.bonuses) if self.before else set()
                return tuple(b for b in self.period.bonuses if b not in old)
            case EventKind.END:
                return ()

    @property
    def removed(self) -> tuple[Bonus, ...]:
        match self.kind:
            case EventKind.START:
                return ()
            case EventKind.CHANGE:
                new = set(self.period.bonuses)
                old = self.before.bonuses if self.before else ()
                return tuple(b for b in old if b not in new)
            case EventKind.END:
                return self.period.bonuses

    @property
    def change_from(self) -> int | None:
        """The percentage this replaces, when a following period differs."""
        if self.kind is EventKind.CHANGE and self.before:
            return self.before.total if self.before.total != self.period.total else None
        return None

    @property
    def is_drop(self) -> bool:
        """Whether a following period gives less than the one it replaces."""
        return self.kind is EventKind.CHANGE and self.to_percent < self.from_percent


def has_release(period: Period) -> bool:
    """Whether any bonus of the period is a release anniversary."""
    return any(isinstance(b, ReleaseBonus) for b in period.bonuses)


def song_events(song: Song, periods: Sequence[Period]) -> Iterator[BonusEvent]:
    """The events of one timeline of a song.

    A period that follows another without a gap is a CHANGE (the new entry
    begins and the old one simply stops); otherwise it STARTs, and a period
    nothing follows ENDs on its last day.
    """
    for i, period in enumerate(periods):
        before = periods[i - 1] if i else None
        after = periods[i + 1] if i + 1 < len(periods) else None

        if before and before.end + ONE_DAY == period.start:
            yield BonusEvent(
                period.start,
                EventKind.CHANGE,
                song.code,
                song.deck_code,
                period,
                before,
            )
        else:
            yield BonusEvent(
                period.start, EventKind.START, song.code, song.deck_code, period
            )

        if not after or after.start != period.end + ONE_DAY:
            yield BonusEvent(
                period.end, EventKind.END, song.code, song.deck_code, period
            )


def timelines(
    song_periods: SongPeriods,
) -> tuple[tuple[Period, ...], tuple[Period, ...]]:
    """``(member periods, periods with an anniversary)`` of a song.

    They are announced separately, as the game's own list shows them: the
    birthday bonus for the deck, and each song's anniversary entry.
    """
    anniversary = tuple(p for p in song_periods.periods if has_release(p))
    return song_periods.member_timeline, anniversary


@dataclass(frozen=True, slots=True, eq=False)
class BonusCalendar:
    """Every song's periods and the events derived from them."""

    songs: Mapping[int, SongPeriods]
    years: tuple[int, ...]
    _events: Mapping[date, tuple[BonusEvent, ...]] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        songs: Mapping[int, SongPeriods],
        years: Iterable[int],
        pace: Callable[[], None] | None = None,
    ) -> BonusCalendar:
        """The calendar for ``songs`` over ``years``.

        ``pace`` is called between songs so a worker thread can rest (see ``Pacer``).
        """
        by_day: dict[date, list[BonusEvent]] = defaultdict(list)
        for sp in songs.values():
            if pace is not None:
                pace()
            for periods in timelines(sp):
                for event in song_events(sp.song, periods):
                    by_day[event.day].append(event)
        order = {EventKind.START: 0, EventKind.CHANGE: 1, EventKind.END: 2}
        events = {
            day: tuple(
                sorted(evs, key=lambda e: (order[e.kind], e.deck_code, e.song_code))
            )
            for day, evs in by_day.items()
        }
        return cls(songs, tuple(sorted(set(years))), events)

    def events_on(self, day: date) -> tuple[BonusEvent, ...]:
        return self._events.get(day, ())

    def days(self) -> list[date]:
        return sorted(self._events)

    def covers(self, day: date) -> bool:
        return bool(self.years) and self.years[0] <= day.year <= self.years[-1]
