"""The birthday and release-anniversary bonus calendar.

This is the pure core of ``bonus_periods.py``. It works on data tables and
dates only, so it needs no clock and no files and is easy to test.

Rules (see :class:`BonusRules`):

* A member birthday gives +2% per artist code, from 3 days before to 3 days
  after the birthday (7 days, inclusive). It is skipped for artists whose
  ``bonusBirthdayUse`` is false or whose ``artistType`` is 4. A null
  ``bonusBirthday`` counts as timestamp 0 (January 1).
* A release anniversary gives +3% over the same window, in years after the
  release year.
* Artist codes of the same person (IRENE Vocal / Dance / Rhythm) are merged
  into one entry and their percentages are added.
* Overlaps are split into separate periods, each listing what is active.
* February 29 events only exist in leap years. Hidden songs are ignored.

Unlike the script, periods are not clipped to a calendar year. A window that
crosses New Year simply is one period, so there are no artificial "ongoing"
events on January 1.
"""

import calendar
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum
from itertools import pairwise
from zoneinfo import ZoneInfo

from games.bonus.decks import (
    DEFAULT_LANGUAGES,
    Deck,
    DeckIndex,
    Entry,
    Song,
    entry_name,
)
from games.bonus.schedule import ms_to_date


@dataclass(frozen=True, slots=True)
class BonusRules:
    window_days: int = 3
    birthday_percent: int = 2
    anniversary_percent: int = 3
    excluded_artist_type: int = 4


DEFAULT_RULES = BonusRules()
ONE_DAY = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class MemberBonus:
    name: str
    birthday: date  # the birth date; only month and day matter
    percent: int
    artist_codes: tuple[int, ...]
    group_code: int | None = None  # set when the member is from another deck


@dataclass(frozen=True, slots=True)
class ReleaseBonus:
    percent: int
    anniversary: int  # the nth anniversary
    release: date


type Bonus = MemberBonus | ReleaseBonus


@dataclass(frozen=True, slots=True)
class Period:
    """A stretch of days (inclusive) with a constant set of active bonuses."""

    start: date
    end: date
    bonuses: tuple[Bonus, ...]

    @property
    def total(self) -> int:
        return sum(b.percent for b in self.bonuses)

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def covers(self, day: date) -> bool:
        return self.start <= day <= self.end


@dataclass(frozen=True, slots=True)
class SongPeriods:
    song: Song
    periods: tuple[Period, ...]
    # The same periods with the release anniversary left out: what a member
    # birthday gives on its own, whatever else the song earns.
    member_periods: tuple[Period, ...] | None = None

    @property
    def member_timeline(self) -> tuple[Period, ...]:
        """The birthday periods; the whole timeline if nothing was split off."""
        return self.periods if self.member_periods is None else self.member_periods


@dataclass(slots=True)
class _Person:
    name: str
    birth: date
    codes: list[int] = field(default_factory=list)
    percent: int = 0
    group_code: int | None = None


def anniversary_in_year(d: date, year: int) -> date | None:
    """The same month and day in ``year``, or None for Feb 29 in a common year."""
    if d.month == 2 and d.day == 29 and not calendar.isleap(year):
        return None
    return date(year, d.month, d.day)


def song_people(
    song: Song,
    artists: Mapping[str, Entry],
    locale: Mapping[str, Entry],
    timezone: ZoneInfo,
    rules: BonusRules = DEFAULT_RULES,
    languages: Sequence[str] = DEFAULT_LANGUAGES,
) -> list[MemberBonus]:
    """The birthday bonuses a song can earn, with same-person codes merged."""
    people: dict[tuple[str, date], _Person] = {}
    for code in song.artist_codes:
        artist = artists.get(str(code))
        if not artist:
            continue
        if (
            not artist.get("bonusBirthdayUse")
            or artist.get("artistType") == rules.excluded_artist_type
        ):
            continue
        birth = ms_to_date(artist.get("bonusBirthday") or 0, timezone)
        assert birth is not None
        name = entry_name(locale, artist, languages) or f"Artist {code}"
        person = people.setdefault(
            (name, birth),
            _Person(name, birth, group_code=_int_or_none(artist.get("group"))),
        )
        person.codes.append(code)
        person.percent += rules.birthday_percent

    return [
        MemberBonus(
            name=p.name,
            birthday=p.birth,
            percent=p.percent,
            artist_codes=tuple(p.codes),
            group_code=p.group_code if p.group_code != song.deck_code else None,
        )
        for p in people.values()
    ]


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def periods_for(
    song: Song,
    members: Iterable[MemberBonus],
    years: Iterable[int],
    rules: BonusRules = DEFAULT_RULES,
    *,
    include_release: bool = True,
) -> tuple[Period, ...]:
    """Split the bonus windows of ``years`` into non-overlapping periods.

    Windows are built for the neighbouring years too, so one that crosses a
    year boundary is complete. Periods are not clipped.
    """
    members = tuple(members)
    wanted = sorted(set(years))
    if not wanted:
        return ()
    span = range(wanted[0] - 1, wanted[-1] + 2)
    delta = timedelta(days=rules.window_days)

    intervals: list[tuple[date, date, Bonus]] = []
    for year in span:
        for member in members:
            centre = anniversary_in_year(member.birthday, year)
            if centre:
                intervals.append((centre - delta, centre + delta, member))
        if include_release and song.release and year > song.release.year:
            centre = anniversary_in_year(song.release, year)
            if centre:
                bonus = ReleaseBonus(
                    rules.anniversary_percent, year - song.release.year, song.release
                )
                intervals.append((centre - delta, centre + delta, bonus))
    if not intervals:
        return ()

    # Sweep the cuts in date order, keeping the intervals that cover each stretch
    # (comparing every cut with every interval is quadratic, and this runs for
    # every song of every game).
    starting: dict[date, list[int]] = defaultdict(list)
    ending: dict[date, list[int]] = defaultdict(list)
    for index, (start, end, _) in enumerate(intervals):
        starting[start].append(index)
        ending[end + ONE_DAY].append(index)
    cuts = sorted(starting.keys() | ending.keys())
    covering: set[int] = set()
    periods: list[Period] = []
    for left, right in pairwise(cuts):
        covering.difference_update(ending.get(left, ()))
        covering.update(starting.get(left, ()))
        if covering:  # in the order the intervals were made
            active = tuple(intervals[i][2] for i in sorted(covering))
            periods.append(Period(left, right - ONE_DAY, active))
    return tuple(periods)


def build_song_periods(
    index: DeckIndex,
    artists: Mapping[str, Entry],
    locale: Mapping[str, Entry],
    years: Iterable[int],
    rules: BonusRules = DEFAULT_RULES,
    languages: Sequence[str] = DEFAULT_LANGUAGES,
    pace: Callable[[], None] | None = None,
) -> dict[int, SongPeriods]:
    """Periods for every visible song that has any (keyed by song code).

    ``pace`` is called between songs (see ``tuning``).
    """
    years = tuple(years)
    result: dict[int, SongPeriods] = {}
    for song in index.songs.values():
        if pace is not None:
            pace()
        if song.is_hidden:
            continue
        members = song_people(song, artists, locale, index.timezone, rules, languages)
        periods = periods_for(song, members, years, rules)
        if not periods:
            continue
        has_release = any(
            isinstance(b, ReleaseBonus) for p in periods for b in p.bonuses
        )
        member_periods = (
            periods_for(song, members, years, rules, include_release=False)
            if has_release
            else periods
        )
        result[song.code] = SongPeriods(song, periods, member_periods)
    return result


# ---------------------------------------------------------------------------
# Calendar events: what changes on which day
# ---------------------------------------------------------------------------


class EventKind(StrEnum):
    START = "start"  # a bonus begins on a song that had none
    CHANGE = "change"  # the active set or the total changes
    END = "end"  # the last active day; the bonus ends after it


@dataclass(frozen=True, slots=True)
class BonusEvent:
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


# ---------------------------------------------------------------------------
# Deck-level view: songs that share a bonus are shown together
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BonusEntry:
    deck_code: int
    start: date
    end: date
    bonuses: tuple[Bonus, ...]
    song_codes: tuple[int, ...]
    all_songs: bool  # covers every visible song of the deck
    before: int | None = None  # the percentage of the period it follows, if different

    @property
    def total(self) -> int:
        return sum(b.percent for b in self.bonuses)

    @property
    def has_release(self) -> bool:
        return any(isinstance(b, ReleaseBonus) for b in self.bonuses)

    @property
    def members(self) -> tuple[MemberBonus, ...]:
        return tuple(b for b in self.bonuses if isinstance(b, MemberBonus))

    def status(self, today: date) -> str:
        if self.end < today:
            return "expired"
        return "upcoming" if self.start > today else "active"


def previous_total(timeline: Sequence[Period], period: Period) -> int | None:
    """The total of the period that runs up to ``period``, if it differs."""
    for other in timeline:
        if other.end + ONE_DAY == period.start and other.total != period.total:
            return other.total
    return None


def deck_entries(
    deck: Deck,
    calendar_: BonusCalendar,
    first: date,
    last: date,
) -> list[BonusEntry]:
    """A deck's bonus entries that overlap ``[first, last]``.

    Two kinds, as the game's own bonus lists show them:

    * member birthdays, shared by every song they apply to ("All Songs" when
      that is the whole deck), and
    * songs that also have a release anniversary, one entry per song with the
      total they earn at that time.
    """
    visible = {s.code for s in deck.visible_songs}
    members: dict[tuple[date, date, tuple[Bonus, ...], int | None], list[int]] = (
        defaultdict(list)
    )
    entries: list[BonusEntry] = []
    for code in visible:
        sp = calendar_.songs.get(code)
        if not sp:
            continue
        for period in sp.member_timeline:
            if period.end >= first and period.start <= last:
                before = previous_total(sp.member_timeline, period)
                members[(period.start, period.end, period.bonuses, before)].append(code)
        anniversaries = [p for p in sp.periods if has_release(p)]
        for period in anniversaries:
            if period.end < first or period.start > last:
                continue
            entries.append(
                BonusEntry(
                    deck_code=deck.code,
                    start=period.start,
                    end=period.end,
                    bonuses=period.bonuses,
                    song_codes=(code,),
                    all_songs=False,  # an anniversary entry is about its song
                    before=previous_total(anniversaries, period),
                )
            )

    entries += [
        BonusEntry(
            deck_code=deck.code,
            start=start,
            end=end,
            bonuses=bonuses,
            song_codes=tuple(sorted(codes)),
            all_songs=set(codes) == visible,
            before=before,
        )
        for (start, end, bonuses, before), codes in members.items()
    ]
    entries.sort(key=lambda e: (e.end, e.start, e.song_codes))  # songs by code
    return entries


def max_score(base: int, percent: int, live_theme: int = 0) -> int:
    """``base`` score with a bonus applied, plus the live theme bonus."""
    if not base:
        return 0
    return base + base * percent // 100 + live_theme


TOP_POSITIONS = 5


def top_scores(scores: Mapping[int, int]) -> tuple[dict[int, list[int]], int]:
    """Rank decks by score, with ties sharing a position.

    Returns ``({score: [deck codes]}`` for the top positions (best first),
    and the sum of the best :data:`TOP_POSITIONS` scores).
    """
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    ranked: dict[int, list[int]] = {}
    position, remaining, total, best = 1, TOP_POSITIONS, 0, None
    for deck, score in ordered:
        if best is not None and score < best:
            position += len(ranked[best])
        if position > TOP_POSITIONS:
            break
        best = score
        ranked.setdefault(score, []).append(deck)
        if remaining:
            total += score
            remaining -= 1
    return ranked, total
