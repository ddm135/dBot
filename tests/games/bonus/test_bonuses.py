import random
from datetime import date

import pytest

from games.bonus.entries import deck_entries, max_score
from games.bonus.events import BonusCalendar, EventKind
from games.bonus.periods import (
    BonusRules,
    MemberBonus,
    ReleaseBonus,
    anniversary_in_year,
    build_song_periods,
    periods_for,
    song_people,
)
from games.data.decks import build_deck_index
from tests.data import KST, Tables, d
from tests.reference import bonus_periods as reference


def make(year_range=(2025,), **kw):
    t = Tables()
    t.group(1, "Deck")
    t.artist(10, "Irene", 1, birthday=(1991, 3, 29))
    t.artist(11, "Irene", 1, birthday=(1991, 3, 29))
    t.artist(12, "Seulgi", 1, birthday=(1994, 2, 10))
    t.song(100, "Song", 1, release=(2020, 3, 26), artists=[10, 11, 12])
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    return t, tables, index


def periods(tables, index, years):
    return build_song_periods(index, tables["ArtistData"], tables["LocaleData"], years)


def test_anniversary_skips_feb_29_in_common_years():
    assert anniversary_in_year(d(2000, 2, 29), 2023) is None
    assert anniversary_in_year(d(2000, 2, 29), 2024) == d(2024, 2, 29)
    assert anniversary_in_year(d(2000, 5, 1), 2023) == d(2023, 5, 1)


def test_same_person_codes_merge_and_add_percent():
    _t, tables, index = make()
    people = song_people(
        index.songs[100], tables["ArtistData"], tables["LocaleData"], KST
    )
    irene = next(p for p in people if p.name == "Irene")
    assert irene.percent == 4
    assert irene.artist_codes == (10, 11)
    assert len(people) == 2


def test_excluded_artists_are_skipped():
    t = Tables()
    t.group(1, "D")
    t.artist(1, "Off", 1, use=False)
    t.artist(2, "Type4", 1, artistType=4)
    t.artist(3, "On", 1)
    t.song(1, "s", 1, artists=[1, 2, 3, 99])
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    names = [
        p.name
        for p in song_people(
            index.songs[1], tables["ArtistData"], tables["LocaleData"], KST
        )
    ]
    assert names == ["On"]


def test_null_birthday_means_january_first():
    t = Tables()
    t.group(1, "D")
    t.artist(1, "NoDate", 1, birthday=None)
    t.song(1, "s", 1, artists=[1])
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    (person,) = song_people(
        index.songs[1], tables["ArtistData"], tables["LocaleData"], KST
    )
    assert (person.birthday.month, person.birthday.day) == (1, 1)


def test_member_from_another_deck_is_flagged():
    t = Tables()
    t.group(1, "A")
    t.group(2, "B")
    t.artist(1, "Guest", 2)
    t.artist(2, "Own", 1, birthday=(2000, 1, 1))
    t.song(1, "s", 1, artists=[1, 2])
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    people = {
        p.name: p
        for p in song_people(
            index.songs[1], tables["ArtistData"], tables["LocaleData"], KST
        )
    }
    assert people["Guest"].group_code == 2
    assert people["Own"].group_code is None


def test_window_is_seven_days_inclusive_and_the_release_year_counts():
    t = Tables()
    t.group(1, "D")
    t.song(1, "s", 1, release=(2020, 6, 10))
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    song = index.songs[1]
    (p,) = [x for x in periods_for(song, [], [2022]) if x.start.year == 2022]
    assert (p.start, p.end, p.days, p.total) == (d(2022, 6, 7), d(2022, 6, 13), 7, 3)
    assert p.bonuses == (ReleaseBonus(3),)
    # The release year counts too, and its window includes the days before the release.
    (first,) = [x for x in periods_for(song, [], [2020]) if x.start.year == 2020]
    assert (first.start, first.end, first.total) == (d(2020, 6, 7), d(2020, 6, 13), 3)
    # Nothing before the release year.
    assert not [x for x in periods_for(song, [], [2019]) if x.start.year == 2019]


def test_overlap_splits_into_separate_periods_with_the_right_totals():
    t = Tables()
    t.group(1, "D")
    t.artist(1, "Mem", 1, birthday=(1999, 6, 12))
    t.song(1, "s", 1, release=(2020, 6, 10), artists=[1])
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    result = periods(tables, index, [2023])[1].periods
    in_2023 = [p for p in result if p.start.year == 2023]
    assert [(p.start, p.end, p.total) for p in in_2023] == [
        (d(2023, 6, 7), d(2023, 6, 8), 3),
        (d(2023, 6, 9), d(2023, 6, 13), 5),
        (d(2023, 6, 14), d(2023, 6, 15), 2),
    ]


def test_a_window_across_new_year_is_one_period():
    t = Tables()
    t.group(1, "D")
    t.song(1, "s", 1, release=(2020, 1, 1))
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    result = periods(tables, index, [2023])[1].periods
    crossing = [p for p in result if p.start == d(2022, 12, 29)]
    assert [(p.start, p.end) for p in crossing] == [(d(2022, 12, 29), d(2023, 1, 4))]


def test_hidden_songs_are_ignored():
    t = Tables()
    t.group(1, "D")
    t.song(1, "s", 1, hidden=True)
    t.song(2, "v", 1)
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    assert set(periods(tables, index, [2023])) == {2}


def test_custom_rules_change_window_and_percent():
    t = Tables()
    t.group(1, "D")
    t.song(1, "s", 1, release=(2020, 6, 10))
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    rules = BonusRules(window_days=1, anniversary_percent=5)
    (p,) = [
        x
        for x in periods_for(index.songs[1], [], [2022], rules)
        if x.start.year == 2022
    ]
    assert (p.start, p.end, p.total) == (d(2022, 6, 9), d(2022, 6, 11), 5)


def test_no_years_or_no_sources_gives_no_periods():
    t = Tables()
    t.group(1, "D")
    t.song(1, "s", 1, release=(2030, 6, 1))
    index = build_deck_index(t.as_tables(), KST)
    assert periods_for(index.songs[1], [], []) == ()
    assert periods_for(index.songs[1], [], [2025]) == ()


# --- events -----------------------------------------------------------------


def _calendar(tables, index, years):
    return BonusCalendar.build(periods(tables, index, years), years)


def test_the_two_timelines_have_their_own_events():
    t = Tables()
    t.group(1, "D")
    t.artist(1, "Mem", 1, birthday=(1999, 6, 12))
    t.song(1, "s", 1, release=(2020, 6, 10), artists=[1])
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    cal = _calendar(tables, index, [2023])

    def kinds(day):
        return [(e.kind, e.from_percent, e.to_percent) for e in cal.events_on(day)]

    # The anniversary entry: 3% (June 7-8), then 5% (June 9-13).
    assert kinds(d(2023, 6, 7)) == [(EventKind.START, 0, 3)]
    assert kinds(d(2023, 6, 8)) == []  # it runs straight into the next one
    assert kinds(d(2023, 6, 13)) == [(EventKind.END, 5, 0)]
    # The birthday entry, June 9-15, is its own timeline.
    assert kinds(d(2023, 6, 9)) == [(EventKind.START, 0, 2), (EventKind.CHANGE, 3, 5)]
    assert kinds(d(2023, 6, 15)) == [(EventKind.END, 2, 0)]
    assert kinds(d(2023, 6, 16)) == []

    change = next(e for e in cal.events_on(d(2023, 6, 9)) if e.kind is EventKind.CHANGE)
    assert [type(b) for b in change.added] == [MemberBonus]
    assert change.removed == ()


def test_events_on_new_year_have_no_artificial_boundary():
    t = Tables()
    t.group(1, "D")
    t.song(1, "s", 1, release=(2020, 1, 1))
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    cal = _calendar(tables, index, [2023])
    assert cal.events_on(d(2023, 1, 1)) == ()
    assert [e.kind for e in cal.events_on(d(2022, 12, 29))] == [EventKind.START]
    assert [e.kind for e in cal.events_on(d(2023, 1, 4))] == [EventKind.END]


def test_calendar_coverage():
    _t, tables, index = make()
    cal = _calendar(tables, index, [2025])
    assert cal.covers(d(2025, 6, 1)) and not cal.covers(d(2027, 1, 1))
    assert cal.days() == sorted(cal.days())


# --- deck entries -----------------------------------------------------------


def test_songs_with_the_same_bonus_share_an_entry():
    t = Tables()
    t.group(1, "D")
    t.artist(1, "Mem", 1, birthday=(1999, 6, 12))
    t.song(1, "a", 1, release=(2010, 1, 1), artists=[1])
    t.song(2, "b", 1, release=(2011, 1, 1), artists=[1])
    t.song(3, "c", 1, release=(2012, 1, 1))  # no member bonus
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    cal = _calendar(tables, index, [2023])
    entries = deck_entries(index.decks[1], cal, d(2023, 6, 1), d(2023, 6, 30))
    birthday = [e for e in entries if e.members]
    assert len(birthday) == 1
    assert birthday[0].song_codes == (1, 2)
    assert not birthday[0].all_songs
    assert birthday[0].total == 2


def test_an_entry_covering_every_visible_song_is_all_songs():
    t = Tables()
    t.group(1, "D")
    t.artist(1, "Mem", 1, birthday=(1999, 6, 12))
    t.song(1, "a", 1, release=(2023, 1, 1), artists=[1])
    t.song(2, "b", 1, release=(2023, 1, 1), artists=[1])
    t.song(3, "h", 1, release=(2023, 1, 1), artists=[], hidden=True)
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    cal = _calendar(tables, index, [2023])
    (entry,) = deck_entries(index.decks[1], cal, d(2023, 6, 1), d(2023, 6, 30))
    assert entry.all_songs and entry.song_codes == (1, 2)


def test_entries_are_filtered_by_range_and_sorted_by_end_then_start():
    t = Tables()
    t.group(1, "D")
    t.artist(1, "A", 1, birthday=(1999, 6, 20))
    t.artist(2, "B", 1, birthday=(1999, 3, 5))
    t.song(1, "s", 1, release=(2030, 1, 1), artists=[1, 2])
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    cal = _calendar(tables, index, [2023])
    entries = deck_entries(index.decks[1], cal, d(2023, 1, 1), d(2023, 12, 31))
    assert [e.members[0].name for e in entries] == ["B", "A"]
    only_june = deck_entries(index.decks[1], cal, d(2023, 6, 1), d(2023, 6, 30))
    assert [e.members[0].name for e in only_june] == ["A"]
    assert only_june[0].status(d(2023, 6, 1)) == "upcoming"
    assert only_june[0].status(d(2023, 6, 20)) == "active"
    assert only_june[0].status(d(2023, 7, 1)) == "expired"


def test_max_score():
    assert max_score(1_000_000, 5, 100) == 1_050_100
    assert max_score(0, 5, 100) == 0


# --- differential test against the original script ---------------------------


def _random_tables(seed):
    rng = random.Random(seed)
    t = Tables()
    for g in (1, 2):
        t.group(g, f"Deck{g}")
    code = 100
    for person in range(12):
        if rng.random() > 0.9:
            birth = (rng.choice([2000, 2004]), 2, 29)
        else:
            birth = (
                rng.choice([1985, 1993, 1999]),
                rng.randint(1, 12),
                rng.randint(1, 28),
            )
        t.artist(
            code,
            f"P{person}",
            rng.choice([1, 2]),
            birthday=birth if rng.random() > 0.1 else None,
            use=rng.random() > 0.15,
            **({"artistType": 4} if rng.random() > 0.9 else {}),
        )
        code += 1
        if rng.random() > 0.5:  # a second artist code for the same person
            t.artist(code, f"P{person}", rng.choice([1, 2]), birthday=birth, use=True)
            code += 1
    artists = list(t.artists)
    for s in range(60):
        rel = (
            rng.choice([2016, 2019, 2022, 2025]),
            rng.randint(1, 12),
            rng.randint(1, 28),
        )
        t.song(
            s + 1,
            f"S{s}",
            rng.choice([1, 2]),
            release=rel,
            artists=[int(a) for a in rng.sample(artists, rng.randint(0, 4))],
            hidden=rng.random() > 0.9,
        )
    return t


@pytest.mark.parametrize("seed", range(8))
@pytest.mark.parametrize("year", [2024, 2025])
def test_matches_the_reference_script_inside_a_year(seed, year):
    t = _random_tables(seed)
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    mine = periods(tables, index, [year])

    artists = {k: v for k, v in tables["ArtistData"].items()}
    groups = {k: v for k, v in tables["GroupData"].items()}
    locale = tables["LocaleData"]
    first, last = date(year, 1, 1), date(year, 12, 31)

    for song in tables["MusicData"].values():
        if song["isHidden"]:
            continue
        expected = reference.build_song_periods(song, artists, groups, locale, year)
        got = []
        if song["code"] in mine:
            for p in mine[song["code"]].periods:
                s, e = max(p.start, first), min(p.end, last)
                if s <= e:
                    got.append(
                        (
                            s,
                            e,
                            p.total,
                            sorted(
                                b.name if isinstance(b, MemberBonus) else "release"
                                for b in p.bonuses
                            ),
                        )
                    )
        want = [
            (
                date.fromisoformat(p["start"]),
                date.fromisoformat(p["end"]),
                p["totalPercent"],
                sorted(b.get("name", "release") for b in p["bonuses"]),
            )
            for p in expected
        ]
        assert got == want, song["code"]


def test_a_swap_keeps_what_was_added_and_removed():
    from games.bonus.events import BonusEvent
    from games.bonus.periods import Period

    release = ReleaseBonus(3)
    member = MemberBonus("M", d(2000, 1, 1), 3, (1,))
    before = Period(d(2023, 1, 1), d(2023, 1, 3), (release,))
    after = Period(d(2023, 1, 4), d(2023, 1, 6), (member,))
    swap = BonusEvent(d(2023, 1, 4), EventKind.CHANGE, 1, 1, after, before)
    assert (swap.from_percent, swap.to_percent) == (3, 3)
    assert swap.added == (member,) and swap.removed == (release,)


def test_entries_include_periods_touching_the_range_edges():
    t = Tables()
    t.group(1, "D")
    t.artist(1, "Mem", 1, birthday=(1999, 6, 12))
    t.song(1, "s", 1, release=(2030, 1, 1), artists=[1])
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    cal = _calendar(tables, index, [2023])  # the window is June 9 - 15
    deck = index.decks[1]
    assert deck_entries(
        deck, cal, d(2023, 6, 15), d(2023, 6, 20)
    )  # starts on its last day
    assert deck_entries(
        deck, cal, d(2023, 6, 1), d(2023, 6, 9)
    )  # ends on its first day
    assert not deck_entries(deck, cal, d(2023, 6, 16), d(2023, 6, 20))
    assert not deck_entries(deck, cal, d(2023, 6, 1), d(2023, 6, 8))


def test_birthday_is_one_all_songs_entry_and_anniversaries_are_per_song():
    """The layout of the game's own list: a deck-wide birthday, plus one
    entry for each song that also has an anniversary."""
    t = Tables()
    t.group(1, "D")
    t.artist(1, "Yuta", 1, birthday=(1995, 10, 26))
    t.song(1, "a", 1, release=(2020, 10, 26), artists=[1])  # anniversary too
    t.song(2, "b", 1, release=(2020, 10, 27), artists=[1])  # anniversary too
    t.song(3, "c", 1, release=(2030, 1, 1), artists=[1])
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    cal = _calendar(tables, index, [2026])
    entries = deck_entries(index.decks[1], cal, d(2026, 10, 25), d(2026, 10, 25))
    birthday = [e for e in entries if not e.has_release]
    assert len(birthday) == 1 and birthday[0].all_songs
    assert (birthday[0].start, birthday[0].end, birthday[0].total) == (
        d(2026, 10, 23),
        d(2026, 10, 29),
        2,
    )
    per_song = sorted((e.song_codes, e.total) for e in entries if e.has_release)
    assert per_song and all(len(codes) == 1 for codes, _ in per_song)
    assert {codes for codes, _ in per_song} == {(1,), (2,)}
    assert not any(e.all_songs for e in entries if e.has_release)


def test_member_entries_do_not_depend_on_release_anniversaries():
    t = Tables()
    t.group(1, "D")
    t.artist(1, "Mem", 1, birthday=(1999, 6, 12))
    t.song(1, "a", 1, release=(2020, 6, 12), artists=[1])
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    cal = _calendar(tables, index, [2023])
    (member,) = [
        e
        for e in deck_entries(index.decks[1], cal, d(2023, 6, 1), d(2023, 6, 30))
        if not e.has_release
    ]
    assert (member.start, member.end, member.total) == (
        d(2023, 6, 9),
        d(2023, 6, 15),
        2,
    )


def _quadratic_periods(song, members, years, rules, include_release=True):
    """The first version of periods_for, kept to check the faster one against."""
    from datetime import timedelta
    from itertools import pairwise

    from games.bonus.periods import ONE_DAY, Period

    wanted = sorted(set(years))
    delta = timedelta(days=rules.window_days)
    intervals = []
    for year in range(wanted[0] - 1, wanted[-1] + 2):
        for member in members:
            centre = anniversary_in_year(member.birthday, year)
            if centre:
                intervals.append((centre - delta, centre + delta, member))
        if include_release and song.release and year >= song.release.year:
            centre = anniversary_in_year(song.release, year)
            if centre:
                bonus = ReleaseBonus(rules.anniversary_percent)
                intervals.append((centre - delta, centre + delta, bonus))
    cuts = sorted({s for s, _, _ in intervals} | {e + ONE_DAY for _, e, _ in intervals})
    out = []
    for left, right in pairwise(cuts):
        last = right - ONE_DAY
        active = tuple(b for s, e, b in intervals if s <= left and last <= e)
        if active:
            out.append(Period(left, last, active))
    return tuple(out)


def test_the_sweep_gives_exactly_the_periods_the_quadratic_scan_gave():
    from types import SimpleNamespace

    rng = random.Random(7)
    rules = BonusRules()
    for _ in range(300):
        members = [
            MemberBonus(
                f"M{i}",
                date(rng.randint(1985, 2005), rng.randint(1, 12), rng.randint(1, 28)),
                rng.choice([5, 10]),
                (i,),
            )
            for i in range(rng.randint(0, 12))
        ]
        release = (
            date(rng.randint(2012, 2024), rng.randint(1, 12), rng.randint(1, 28))
            if rng.random() < 0.7
            else None
        )
        song = SimpleNamespace(release=release)
        years = range(2025, 2025 + rng.randint(1, 3))
        for include_release in (True, False):
            expected = _quadratic_periods(song, members, years, rules, include_release)
            got = periods_for(
                song, members, years, rules, include_release=include_release
            )
            assert got == expected


def test_a_paced_build_gives_the_same_calendar_and_rests_between_songs():
    _, tables, index = make()
    calls: list[int] = []

    def pace() -> None:
        calls.append(1)

    args = (index, tables["ArtistData"], tables["LocaleData"], [2025])
    plain = build_song_periods(*args)
    paced = build_song_periods(*args, pace=pace)
    assert paced == plain
    assert len(calls) == len(index.songs)
    built = BonusCalendar.build(paced, [2025], pace)
    assert len(calls) == len(index.songs) + len(paced)
    assert built.songs == plain


def _names(song_code, tables, index):
    return sorted(
        p.name
        for p in song_people(
            index.songs[song_code], tables["ArtistData"], tables["LocaleData"], KST
        )
    )


def test_a_person_is_named_by_their_codes_when_the_song_has_only_some():
    t = Tables()
    t.group(1, "D")
    for position, part in enumerate(("Vocal", "Dance", "Rhythm")):
        t.locale[str(51003001 + position)] = {"koKR": part, "enUS": part}
    for code, position in ((10, 0), (11, 1), (12, 2)):
        t.artist(code, "Irene", 1, position=position)
    t.artist(20, "Solo", 1)
    t.song(1, "a", 1, artists=[10, 20])
    t.song(2, "b", 1, artists=[11])
    t.song(3, "c", 1, artists=[10, 11])
    t.song(4, "d", 1, artists=[10, 11, 12])
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    assert _names(1, tables, index) == ["Irene Vocal", "Solo"]
    assert _names(2, tables, index) == ["Irene Dance"]
    assert _names(3, tables, index) == ["Irene Vocal + Irene Dance"]  # in code order
    assert _names(4, tables, index) == ["Irene"]  # all of them: the person


def test_songs_with_different_codes_of_a_person_are_separate_entries():
    t = Tables()
    t.group(1, "D")
    for position, part in enumerate(("Vocal", "Dance")):
        t.locale[str(51003001 + position)] = {"koKR": part, "enUS": part}
    for code, position in ((10, 0), (11, 1)):
        t.artist(code, "Irene", 1, birthday=(1991, 3, 29), position=position)
    t.song(1, "S1", 1, release=(2030, 1, 1), artists=[10])
    t.song(2, "S2", 1, release=(2030, 1, 1), artists=[11])
    t.song(3, "S3", 1, release=(2030, 1, 1), artists=[10])
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    cal = _calendar(tables, index, [2026])
    entries = deck_entries(index.decks[1], cal, d(2026, 1, 1), d(2026, 12, 31))
    got = sorted((e.members[0].name, e.song_codes) for e in entries)
    assert got == [("Irene Dance", (2,)), ("Irene Vocal", (1, 3))]


def test_a_code_without_position_text_is_named_by_its_analytics_name():
    t = Tables()
    t.group(1, "D")
    t.artist(10, "Gu", 1, position=3, analyticsData="Gu Guitar")  # no text for 3
    t.artist(11, "Gu", 1, position=0, analyticsData="Gu Vocal")
    t.artist(12, "Plain", 1)
    t.artist(13, "Plain", 1, position=None)
    t.song(1, "a", 1, artists=[10])
    t.song(2, "b", 1, artists=[12])
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    assert _names(1, tables, index) == ["Gu Guitar"]
    assert _names(2, tables, index) == ["Plain"]  # a name only, whatever is missing


def test_a_game_can_say_which_text_names_a_position():
    t = Tables()
    t.group(1, "D")
    t.locale["51003002"] = {"enUS": "GUITAR", "koKR": "GUITAR"}
    t.artist(10, "Gu", 1, position=3)
    t.artist(11, "Gu", 1, position=0, analyticsData="Gu Vocal")
    t.song(1, "a", 1, artists=[10])
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    (person,) = song_people(
        index.songs[1],
        tables["ArtistData"],
        tables["LocaleData"],
        KST,
        positions={3: 51003002},
    )
    assert person.name == "Gu GUITAR"


def test_ebidan_names_position_3_with_the_guitar_text():
    from games.registry import GAMES

    assert GAMES["EB"].position_locale[3] == 51003002
    assert GAMES["SM"].position_locale == {0: 51003001, 1: 51003002, 2: 51003003}
