"""The bonus rules and the periods they make for a song.

It works on data tables and dates only, so it needs no clock and no files.

Rules (see :class:`BonusRules`):

* A member birthday gives +2% per artist code, from 3 days before to 3 days
  after the birthday (7 days, inclusive). It is skipped for artists whose
  ``bonusBirthdayUse`` is false or whose ``artistType`` is 4. A null
  ``bonusBirthday`` counts as timestamp 0 (January 1).
* A release anniversary gives +3% over the same window, from the release year
  on (the release day itself is the first one).
* Artist codes of the same person (IRENE Vocal / Dance / Rhythm) are merged
  into one entry and their percentages are added. It is named after the person
  when the song has all of their codes, and after the codes it has (``IRENE Vocal``)
  when it has only some, so songs with different codes are listed apart.
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
    EXCLUDED_ARTIST_TYPE,
    DeckIndex,
    Song,
    entry_name,
    locale_text,
)
from games.data.schedule import ms_to_date
from games.models import POSITION_LOCALE, Entry


@dataclass(frozen=True, slots=True)
class BonusRules:
    """The numbers of the bonus rules: window length, percentages, and the artist type that
    gets none.
    """

    window_days: int = 3
    birthday_percent: int = 2
    anniversary_percent: int = 3
    excluded_artist_type: int = EXCLUDED_ARTIST_TYPE


DEFAULT_RULES = BonusRules()
ONE_DAY = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class MemberBonus:
    """A member's birthday bonus: who, the birthday, the percentage and the artist codes it
    applies to. ``name`` is the person, or the codes of theirs the song has (``IRENE
    Vocal``) when it has only some of them.
    """

    name: str
    birthday: date  # the birth date; only month and day matter
    percent: int
    artist_codes: tuple[int, ...]
    group_code: int | None = None  # set when the member is from another deck


@dataclass(frozen=True, slots=True)
class ReleaseBonus:
    """A release anniversary bonus (the release day itself counts as the first)."""

    percent: int


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


type PersonKey = tuple[str, date]  # the name and birthday that make up one person


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


def _person_key(
    code: int,
    artist: Entry,
    locale: Mapping[str, Entry],
    timezone: ZoneInfo,
    rules: BonusRules,
    languages: Sequence[str],
) -> PersonKey | None:
    """Who an artist code is, or None if it earns no birthday bonus."""
    if (
        not artist.get("bonusBirthdayUse")
        or artist.get("artistType") == rules.excluded_artist_type
    ):
        return None
    birth = ms_to_date(artist.get("bonusBirthday") or 0, timezone)
    assert birth is not None
    return entry_name(locale, artist, languages) or f"Artist {code}", birth


def person_codes(
    artists: Mapping[str, Entry],
    locale: Mapping[str, Entry],
    timezone: ZoneInfo,
    rules: BonusRules = DEFAULT_RULES,
    languages: Sequence[str] = DEFAULT_LANGUAGES,
) -> dict[PersonKey, frozenset[int]]:
    """Every artist code of each person who earns a birthday bonus."""
    roster: dict[PersonKey, set[int]] = defaultdict(set)
    for key, artist in artists.items():
        code = int(key)
        if person := _person_key(code, artist, locale, timezone, rules, languages):
            roster[person].add(code)
    return {person: frozenset(codes) for person, codes in roster.items()}


def song_people(
    song: Song,
    artists: Mapping[str, Entry],
    locale: Mapping[str, Entry],
    timezone: ZoneInfo,
    rules: BonusRules = DEFAULT_RULES,
    languages: Sequence[str] = DEFAULT_LANGUAGES,
    roster: Mapping[PersonKey, frozenset[int]] | None = None,
    positions: Mapping[int, int] = POSITION_LOCALE,
) -> list[MemberBonus]:
    """The birthday bonuses a song can earn, with same-person codes merged.

    A person is named as themselves when the song has all of their codes, and by
    the codes it has when it has only some (``roster`` is every code of each
    person, from :func:`person_codes`; it is worked out here if not given).
    """
    if roster is None:
        roster = person_codes(artists, locale, timezone, rules, languages)
    people: dict[PersonKey, _Person] = {}
    for code in song.artist_codes:
        artist = artists.get(str(code))
        if not artist:
            continue
        key = _person_key(code, artist, locale, timezone, rules, languages)
        if key is None:
            continue
        person = people.setdefault(key, _Person(*key, group_code=_group_of(artist)))
        person.codes.append(code)
        person.percent += rules.birthday_percent

    return [
        MemberBonus(
            name=_label(p, key, artists, roster, locale, languages, positions),
            birthday=p.birth,
            percent=p.percent,
            artist_codes=tuple(p.codes),
            group_code=p.group_code if p.group_code != song.deck_code else None,
        )
        for key, p in people.items()
    ]


def _label(
    person: _Person,
    key: PersonKey,
    artists: Mapping[str, Entry],
    roster: Mapping[PersonKey, frozenset[int]],
    locale: Mapping[str, Entry],
    languages: Sequence[str],
    positions: Mapping[int, int],
) -> str:
    """The person's name, or the names of the codes the song has if not all of them."""
    if roster.get(key, frozenset()) <= set(person.codes):
        return person.name
    return " + ".join(
        _code_name(artists[str(code)], person.name, locale, languages, positions)
        for code in sorted(person.codes)
    )


def _code_name(
    artist: Entry,
    name: str,
    locale: Mapping[str, Entry],
    languages: Sequence[str],
    positions: Mapping[int, int],
) -> str:
    """One artist code as ``<name> <position>`` (``IRENE Vocal``).

    The position is the artist's ``position`` number (0, 1, 2: Vocal, Dance,
    Rhythm) as the game's own text for it (``positions`` says which text). Without
    one, ``analyticsData`` has the full name, and failing that the person's name is
    all there is.
    """
    position = artist.get("position")
    code = positions.get(position) if isinstance(position, int) else None
    text = locale_text(locale, code, None, languages) if code is not None else None
    if text:
        return f"{name} {text}"
    analytics = artist.get("analyticsData")
    return analytics if isinstance(analytics, str) else name


def _group_of(artist: Entry) -> int | None:
    group = artist.get("group")
    return group if isinstance(group, int) else None


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
        if include_release and song.release and year >= song.release.year:
            centre = anniversary_in_year(song.release, year)
            if centre:
                bonus = ReleaseBonus(rules.anniversary_percent)
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
    positions: Mapping[int, int] = POSITION_LOCALE,
) -> dict[int, SongPeriods]:
    """Periods for every visible song that has any (keyed by song code).

    ``pace`` is called between songs (see ``ops.tuning.Pacer``).
    """
    years = tuple(years)
    roster = person_codes(artists, locale, index.timezone, rules, languages)
    result: dict[int, SongPeriods] = {}
    for song in index.songs.values():
        if pace is not None:
            pace()
        if song.is_hidden:
            continue
        members = song_people(
            song, artists, locale, index.timezone, rules, languages, roster, positions
        )
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
