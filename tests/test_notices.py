from dataclasses import replace

from games.bonuses import BonusCalendar, build_song_periods
from games.decks import build_deck_index
from games.notices import deck_notices, hours_due, notices_for_day

from .data import KST, Tables, d


def fixture():
    """Deck 1: a birthday (June 9-15) on three songs, and song 3 also has an
    anniversary (June 7-13). Deck 2: a birthday on one song."""
    t = Tables()
    t.group(1, "D1")
    t.group(2, "D2")
    t.artist(1, "Mem", 1, birthday=(1999, 6, 12))
    t.artist(2, "Other", 2, birthday=(1999, 6, 12))
    t.song(1, "a", 1, release=(2030, 1, 1), artists=[1])
    t.song(2, "b", 1, release=(2030, 1, 1), artists=[1])
    t.song(3, "c", 1, release=(2020, 6, 10), artists=[1])
    t.song(4, "x", 2, release=(2030, 1, 1), artists=[2])
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    songs = build_song_periods(
        index, tables["ArtistData"], tables["LocaleData"], [2023]
    )
    return index, BonusCalendar.build(songs, [2023])


def lines(index, cal, day, deck=1):
    return deck_notices(index.decks[deck], cal.events_on(day))


def test_an_anniversary_is_announced_for_its_song_alone():
    index, cal = fixture()
    start = lines(index, cal, d(2023, 6, 7))
    assert start["end"] == []
    (line,) = start["start"]
    assert line.song_codes == (3,) and line.has_release and not line.all_songs
    assert (line.total, line.start, line.end) == (3, d(2023, 6, 7), d(2023, 6, 8))


def test_the_birthday_is_one_all_songs_line_beside_the_anniversary_entry():
    index, cal = fixture()
    nine = lines(index, cal, d(2023, 6, 9))["start"]
    birthday = next(line for line in nine if not line.has_release)
    assert birthday.all_songs and birthday.song_codes == (1, 2, 3)  # song 3 included
    assert [m.name for m in birthday.members] == ["Mem"]
    assert (birthday.total, birthday.start, birthday.end) == (
        2,
        d(2023, 6, 9),
        d(2023, 6, 15),
    )
    song = next(line for line in nine if line.has_release)
    assert song.song_codes == (3,) and song.total == 5
    assert (song.start, song.end) == (d(2023, 6, 9), d(2023, 6, 13))


def test_each_entry_ends_on_its_own_last_day():
    index, cal = fixture()
    (song,) = lines(index, cal, d(2023, 6, 13))["end"]
    assert song.has_release and song.total == 5 and song.song_codes == (3,)
    (birthday,) = lines(index, cal, d(2023, 6, 15))["end"]
    assert not birthday.has_release and birthday.all_songs and birthday.total == 2
    assert birthday.day == d(2023, 6, 15)


def test_an_entry_that_is_followed_by_another_does_not_end():
    index, cal = fixture()
    # The 3% entry (June 7-8) runs straight into the 5% one: only the new one
    # is announced, on the 9th.
    assert lines(index, cal, d(2023, 6, 8)) == {"start": [], "end": []}


def test_other_decks_and_stray_events_are_left_out():
    index, cal = fixture()
    events = cal.events_on(d(2023, 6, 9))
    assert all(
        c.song_codes == (4,)
        for cat in deck_notices(index.decks[2], events).values()
        for c in cat
    )
    assert set(notices_for_day(index.decks, events, [1])) == {1}
    assert notices_for_day(index.decks, events, [99]) == {}
    assert notices_for_day(index.decks, [], [1, 2]) == {}
    stray = replace(events[0], song_code=999)  # not a visible song of the deck
    assert deck_notices(index.decks[events[0].deck_code], [stray]) == {
        "start": [],
        "end": [],
    }


def test_hours_due():
    assert hours_due(23, 1)
    assert not hours_due(22, 1)
    assert hours_due(22, 2) and hours_due(23, 2)  # still due later in the day
    assert not hours_due(5, 0) and not hours_due(23, 0)
    assert hours_due(1, 23) and not hours_due(0, 23)


def test_songs_with_the_same_anniversary_get_a_line_each():
    t = Tables()
    t.group(1, "D")
    for code in (1, 2):
        t.song(code, f"s{code}", 1, release=(2020, 6, 10))
    tables = t.as_tables()
    index = build_deck_index(tables, KST)
    cal = BonusCalendar.build(
        build_song_periods(index, tables["ArtistData"], tables["LocaleData"], [2023]),
        [2023],
    )
    start = deck_notices(index.decks[1], cal.events_on(d(2023, 6, 7)))["start"]
    assert [line.song_codes for line in start] == [
        (1,),
        (2,),
    ]  # as the game's list shows them


def test_hours_due_reaches_two_days_ahead():
    # 30 hours before the day after tomorrow begins is today at 6 pm.
    assert hours_due(18, 30, days_ahead=2) and not hours_due(17, 30, days_ahead=2)
    assert hours_due(1, 47, days_ahead=2) and not hours_due(0, 47, days_ahead=2)
    # for tomorrow, anything of 24 hours or more is already due all day
    assert hours_due(0, 30) and hours_due(23, 47)


def test_a_following_bonus_that_gives_less_counts_as_the_other_ending():
    from types import SimpleNamespace

    from games.bonuses import MemberBonus, Period, song_events
    from games.notices import category_of

    def bonus(percent):
        return (MemberBonus("M", d(1999, 6, 12), percent, (1,)),)

    song = SimpleNamespace(code=1, deck_code=1)
    first = Period(d(2023, 6, 1), d(2023, 6, 3), bonus(7))
    lower = Period(d(2023, 6, 4), d(2023, 6, 6), bonus(5))
    higher = Period(d(2023, 6, 7), d(2023, 6, 9), bonus(8))
    events = {
        e.day: e
        for e in song_events(song, [first, lower, higher])  # type: ignore[arg-type]
    }
    down, up = events[d(2023, 6, 4)], events[d(2023, 6, 7)]
    assert (down.change_from, category_of(down)) == (7, "end")
    assert (up.change_from, category_of(up)) == (5, "start")
    assert category_of(events[d(2023, 6, 1)]) == "start"
    assert events[d(2023, 6, 1)].change_from is None
    assert category_of(events[d(2023, 6, 9)]) == "end"
