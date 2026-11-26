"""The bonus rules and the periods they make for a song.

It works on data tables and dates only, so it needs no clock and no files.

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

Periods are not clipped to a calendar year: a window that crosses New Year is
one period, so there are no artificial "ongoing" events on January 1.
"""

import calendar
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from itertools import pairwise
from zoneinfo import ZoneInfo

from games.data.decks import (
    DEFAULT_LANGUAGES,
    DeckIndex,
    Song,
    entry_name,
)
from games.data.schedule import ms_to_date
from games.models import Entry


@dataclass(frozen=True, slots=True)
class BonusRules:
    """The numbers of the bonus rules: window length, percentages, and the artist type that
    gets none.
    """

    window_days: int = 3
    birthday_percent: int = 2
    anniversary_percent: int = 3
    excluded_artist_type: int = 4


DEFAULT_RULES = BonusRules()
ONE_DAY = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class MemberBonus:
    """A member's birthday bonus: who, the birthday, the percentage and the artist codes it
    applies to.
    """

    name: str
    birthday: date  # the birth date; only month and day matter
    percent: int
    artist_codes: tuple[int, ...]
    group_code: int | None = None  # set when the member is from another deck


@dataclass(frozen=True, slots=True)
class ReleaseBonus:
    """A release anniversary bonus: its percentage, which anniversary, and the release
    date.
    """

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
    """A song's periods, and the same periods without the anniversary (what birthdays give
    on their own).
    """

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

    ``pace`` is called between songs (see ``ops.tuning.Pacer``).
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
