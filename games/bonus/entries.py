"""The deck-level view: songs that share a bonus are shown together, and what it scores."""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from games.bonus.events import BonusCalendar
from games.bonus.periods import (
    ONE_DAY,
    Bonus,
    MemberBonus,
    Period,
    has_release,
    members_of,
)
from games.data.decks import Deck


@dataclass(frozen=True, slots=True)
class BonusEntry:
    """A deck's bonus as listed to users: the songs it covers, its dates and what
    makes it up. ``before`` is the percentage it follows, if that differs.
    """

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
        return has_release(self.bonuses)

    @property
    def members(self) -> tuple[MemberBonus, ...]:
        return members_of(self.bonuses)

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
        anniversaries = [p for p in sp.periods if has_release(p.bonuses)]
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
