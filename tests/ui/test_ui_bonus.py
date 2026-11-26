import dataclasses
from datetime import date, datetime, timedelta

from games.bonus.entries import deck_entries, top_scores
from games.bonus.events import BonusCalendar
from games.bonus.notices import deck_notices
from games.bonus.periods import build_song_periods
from games.charts.song_stats import SongStat
from games.index import build_index
from games.registry import GAMES
from tests.data import Tables, d
from ui.bonus import (
    BLANK,
    DeckEntries,
    chunks,
    entry_icons,
    entry_name,
    entry_value,
    list_embed,
    max_embed,
    month_range,
    notice_embed,
    notice_text,
    pings_embed,
    top_embeds,
    week_range,
    year_range,
)
from ui.text import escape, month_day, truncate

SM = GAMES["SM"]


def setup():
    """TW_ICE: a birthday for Mem (June 9-15) and an anniversary of song 1
    (June 7-13). SOLO: its one member is the deck itself."""
    t = Tables()
    t.group(1, "TW_ICE")
    t.group(2, "SOLO")
    t.artist(1, "Mem", 1, birthday=(1999, 6, 12))
    t.artist(2, "SOLO", 2, birthday=(1999, 6, 12))
    t.song(1, "Cheer *Up*", 1, release=(2020, 6, 10), artists=[1], album=None)
    t.song(2, "Fancy", 1, release=(2030, 1, 1), artists=[1])
    t.song(3, "Solo Song", 2, release=(2030, 1, 1), artists=[2])
    t.locale["777"] = {"koKR": "k", "enUS": "The Album"}
    t.music["1"]["albumName"] = 777
    tables = t.as_tables()
    index = build_index(SM, tables)
    songs = build_song_periods(index.decks, index.artists, index.locale, [2023])
    cal = BonusCalendar.build(songs)
    return index, cal


def entries_of(index, cal, deck, first=None, last=None):
    first, last = first or d(2023, 6, 1), last or d(2023, 6, 30)
    return deck_entries(index.decks.decks[deck], cal, first, last)


def by_kind(entries):
    member = next(e for e in entries if not e.has_release)
    anniversary = [e for e in entries if e.has_release]
    return member, anniversary


# --- text helpers --------------------------------------------------------------------


def test_text_helpers():
    assert (
        escape("a*b_c`d~e|f>g\\h") == "a\\*b\\_c\\`d~e|f>g\\h"
    )  # the three v0 escaped
    assert month_day(date(2025, 6, 7)) == "June 7"
    assert truncate("abcdef", 4) == "abc…" and truncate("ab", 4) == "ab"


def test_ranges():
    assert week_range(d(2026, 10, 25)).first == d(2026, 10, 19)  # a Sunday
    assert week_range(d(2026, 10, 25)).last == d(2026, 10, 26)
    assert week_range(d(2026, 10, 25), weeks_ahead=1).first == d(2026, 10, 26)
    assert (month_range(d(2026, 12, 5)).first, month_range(d(2026, 12, 5)).last) == (
        d(2026, 12, 1),
        d(2026, 12, 31),
    )
    assert month_range(d(2026, 12, 5), months_ahead=1).first == d(2027, 1, 1)
    assert year_range(d(2026, 3, 3)).last == d(2026, 12, 31)


# --- one entry -----------------------------------------------------------------------


def test_entry_names_follow_the_games_own_list():
    index, cal = setup()
    deck = index.decks.decks[1]
    member, (_song, _plain) = by_kind(entries_of(index, cal, 1))
    live = d(2023, 6, 10)
    # A birthday on its own names its members and the songs.
    assert (
        entry_name(member, deck, index, live)
        == ":white_check_mark: Mem: All Songs :birthday:"
    )
    assert entry_name(member, deck, index, live, show_deck=True) == (
        ":white_check_mark: **TW\\_ICE** Mem: All Songs :birthday:"
    )
    # An entry of a song names only the song, with the icons of what it earns.
    both = next(e for e in entries_of(index, cal, 1) if e.has_release and e.members)
    assert (
        entry_name(both, deck, index, live)
        == ":white_check_mark: Cheer \\*Up\\* :birthday: :dvd:"
    )
    only = next(e for e in entries_of(index, cal, 1) if e.has_release and not e.members)
    assert (
        entry_name(only, deck, index, d(2023, 6, 1)) == "Cheer \\*Up\\* :cd:"
    )  # upcoming: no mark
    assert (
        entry_name(only, deck, index, d(2023, 7, 1)) == "~~Cheer \\*Up\\* :cd:~~"
    )  # expired


def test_members_who_are_the_deck_are_not_repeated():
    index, cal = setup()
    solo = index.decks.decks[2]
    (member,) = entries_of(index, cal, 2)
    assert (
        entry_name(member, solo, index, d(2023, 6, 10))
        == ":white_check_mark: All Songs :birthday:"
    )
    assert entry_name(member, solo, index, d(2023, 6, 10), show_deck=True) == (
        ":white_check_mark: **SOLO**: All Songs :birthday:"
    )


def test_a_birthday_that_misses_some_songs_names_them():
    index, cal = setup()
    deck = index.decks.decks[1]
    member, _ = by_kind(entries_of(index, cal, 1))
    from dataclasses import replace

    some = replace(member, song_codes=(2,), all_songs=False)
    assert (
        entry_name(some, deck, index, d(2023, 6, 10))
        == ":white_check_mark: Mem: Fancy :birthday:"
    )
    many = replace(member, song_codes=(1, 2, 2, 2, 2), all_songs=False)
    assert "+2 more" in entry_name(many, deck, index, d(2023, 6, 10))


def test_icons():
    index, cal = setup()
    entries = entries_of(index, cal, 1)
    icons = {(e.has_release, bool(e.members)): entry_icons(e) for e in entries}
    assert icons == {
        (False, True): ":birthday:",
        (True, False): ":cd:",
        (True, True): ":birthday: :dvd:",
    }


def test_entry_values_for_each_status():
    index, cal = setup()
    deck = index.decks.decks[1]
    member, _ = by_kind(entries_of(index, cal, 1))
    base = index.deck_max_score(1)
    kwargs = {"live_theme": 1000}

    expired = entry_value(member, deck, index, today=d(2023, 7, 1), **kwargs)
    assert expired.startswith("~~2% | June 9 - June 15 | ") and expired.endswith(
        "| Expired~~"
    )
    active = entry_value(member, deck, index, today=d(2023, 6, 10), **kwargs)
    assert "Ends <t:" in active and not active.startswith("~~")
    assert f"{base + base * 2 // 100 + 1000:,}" in active
    upcoming = entry_value(
        member, deck, index, today=d(2023, 6, 1), last_day=member.start, **kwargs
    )
    assert "Available <t:" in upcoming and upcoming.endswith(":bangbang:")


# --- /bonus list -----------------------------------------------------------------------


def rows_of(index, cal):
    return [
        (index.decks.decks[c], e) for c in (1, 2) for e in entries_of(index, cal, c)
    ]


def render(index, cal, deck=None, page=1, per_page=5, rows=None):
    return list_embed(
        index,
        index.decks.decks.get(deck) if deck else None,
        rows if rows is not None else rows_of(index, cal),
        first=d(2023, 6, 1),
        last=d(2023, 6, 30),
        today=d(2023, 6, 10),
        live_theme=0,
        icon="http://icon",
        page=page,
        pages=2,
        per_page=per_page,
    )


def test_the_list_embed_is_laid_out_like_v0():
    index, cal = setup()
    embed = render(index, cal)
    assert embed.title == "All Bonuses (June 1 - June 30)"
    assert embed.author.name == f"{SM.name} - Bonus Info"
    assert embed.author.icon_url == "http://icon"
    assert embed.footer.text == "Page 1/2"
    assert embed.color.value == SM.color
    assert embed.description is None
    assert all(
        f.name.startswith(("~~", ":white_check_mark: ", "**")) or f.name
        for f in embed.fields
    )
    assert any(
        f.name.startswith("**") or "**TW\\_ICE**" in f.name for f in embed.fields
    )
    assert len(embed.fields) == len(rows_of(index, cal)) == 4  # all on one page


def test_the_list_embed_for_one_artist_and_for_nothing():
    index, cal = setup()
    embed = render(
        index, cal, deck=2, rows=[r for r in rows_of(index, cal) if r[0].code == 2]
    )
    assert embed.title == "SOLO (June 1 - June 30)"
    assert "**SOLO**" not in embed.fields[0].name  # the artist is in the title
    empty = render(index, cal, rows=[])
    assert empty.description == "None" and empty.fields == []


# --- /bonus top ------------------------------------------------------------------------


def items_of(index, cal):
    return [
        DeckEntries(index.decks.decks[c], entries_of(index, cal, c)) for c in (1, 2)
    ]


def layout(index, cal, items=None, **extra):
    kwargs = {
        "today": d(2023, 6, 10),
        "last_day": d(2023, 6, 30),
        "live_theme": 0,
        "icon": None,
    }
    return top_embeds(
        index,
        items if items is not None else items_of(index, cal),
        **{**kwargs, **extra},
    )


def test_top_fields_are_a_deck_and_bold_entry_lines():
    index, cal = setup()
    (embed,) = layout(index, cal)
    assert embed.title is None and embed.description is None
    assert embed.author.name == f"{SM.name} - Top Bonuses"
    assert embed.footer.text == "Page 1/1"
    first = embed.fields[0]
    assert first.name == "TW\\_ICE"
    lines = first.value.split("\n")
    assert lines[0].startswith("> **") and lines[0].endswith("**")
    assert lines[1].startswith("> ") and "%" in lines[1]
    # Each entry is two quoted lines and a trailing newline.
    assert first.value.endswith("\n")
    assert first.value.count("\n") == 2 * first.value.count("> **")


def test_top_splits_a_deck_with_many_entries_and_keeps_to_discords_limits():
    index, cal = setup()
    deck = index.decks.decks[1]
    entry = entries_of(index, cal, 1)[0]
    many = DeckEntries(deck, [entry] * 40)
    pages = layout(index, cal, [many])
    fields = [f for p in pages for f in p.fields]
    assert fields[0].name == "TW\\_ICE" and all(f.name == BLANK for f in fields[1:])
    assert len(fields) > 1 and all(len(f.value) <= 1024 for f in fields)
    for embed in pages:
        total = sum(len(f.name) + len(f.value) for f in embed.fields) + len(
            embed.author.name
        )
        assert total <= 6000 and len(embed.fields) <= 25
    many_decks = [DeckEntries(deck, [entry])] * 60
    pages = layout(index, cal, many_decks)
    assert len(pages) > 1 and all(len(p.fields) <= 25 for p in pages)
    assert [p.footer.text for p in pages] == [
        f"Page {i}/{len(pages)}" for i in range(1, len(pages) + 1)
    ]


def test_top_with_nothing_says_none():
    index, cal = setup()
    (embed,) = layout(index, cal, [])
    assert embed.description == "None" and embed.fields == []


def test_the_max_score_embed():
    index, _ = setup()
    ranked = {100: [1, 2], 90: [1], 80: [2], 70: [1], 60: [2], 50: [1]}
    embed = max_embed(index, ranked, 123456, None)
    assert embed.title == "Max Score of This Week"
    assert embed.description == "**123,456**"
    assert embed.author.name == f"{SM.name} - Top Bonuses"
    assert [f.name for f in embed.fields] == [
        "**Top 1-2**: 100",
        "**Top 3**: 90",
        "**Top 4**: 80",
        "**Top 5**: 70",
    ]
    assert embed.fields[0].value == "TW\\_ICE, SOLO"
    # A tie that runs past fifth place is still shown as ending at fifth.
    long_tie = max_embed(index, {100: [1, 2, 3, 4, 5, 6, 7]}, 1, None)
    assert [f.name for f in long_tie.fields] == ["**Top 1-5**: 100"]
    ranked, total = top_scores({1: 5, 2: 5})
    assert max_embed(index, ranked, total, None).fields[0].name == "**Top 1-2**: 5"


def test_the_ping_list_embed():
    embed = pings_embed("SUPERSTAR SM", 0x123456, ["A*B", "C"], "http://x")
    assert embed.author.name == "SUPERSTAR SM" and embed.description == "- A\\*B\n- C"
    assert embed.color.value == 0x123456
    assert pings_embed("G", 0, [], None).description == "None"


# --- pings -------------------------------------------------------------------------------


def lines_on(index, cal, day, deck=1):
    return deck_notices(index.decks.decks[deck], cal.events_on(day))


def test_a_birthday_ping_line_names_the_members_and_all_songs():
    index, cal = setup()
    deck = index.decks.decks[1]
    birthday = next(
        l for l in lines_on(index, cal, d(2023, 6, 9))["start"] if not l.has_release
    )
    assert (
        notice_text(birthday, deck, index)
        == "> Mem - **All Songs**\n> 2% | June 9 - June 15\n"
    )


def test_a_song_ping_line_has_the_album_the_song_and_its_length():
    index, cal = setup()
    deck = index.decks.decks[1]
    song = next(
        l for l in lines_on(index, cal, d(2023, 6, 9))["start"] if l.has_release
    )
    stats = {1: SongStat(201)}
    assert notice_text(song, deck, index, stats) == (
        "> The Album - **Cheer \\*Up\\*** (3:21)\n> 3% -> 5% | June 9 - June 13\n"
    )
    # Without stats the length is left out; without an album the deck stands in.
    assert notice_text(song, deck, index).startswith(
        "> The Album - **Cheer \\*Up\\***\n"
    )


def test_the_ping_embed_has_available_and_ending_fields():
    index, _cal = setup()
    deck = index.decks.decks[1]
    day = d(2023, 6, 9)
    texts = {"start": ["> a\n> 2%\n"], "end": ["> b\n> 3%\n"]}
    embed = notice_embed(index, deck, day, texts, "http://emblem")
    assert embed.author.name == "TW\\_ICE" and embed.author.icon_url == "http://emblem"
    assert embed.color.value == SM.color
    start = int(datetime(2023, 6, 9, tzinfo=SM.timezone).timestamp())
    assert embed.fields[0].name == f"Available <t:{start}:R> :green_circle:"
    assert embed.fields[1].name == f"Ends <t:{start + 86400}:R> :orange_circle:"
    assert embed.fields[1].value == "> b\n> 3%\n"
    only_start = notice_embed(index, deck, day, {"start": ["> a\n"]}, None)
    assert [f.name[:9] for f in only_start.fields] == ["Available"]


def test_chunks_never_split_an_entry():
    parts = ["a" * 400, "b" * 400, "c" * 400]
    assert chunks(parts, 1024) == ["a" * 400 + "b" * 400, "c" * 400]
    assert chunks([], 1024) == [] and chunks(["x"], 1024) == ["x"]
    assert timedelta(days=1).days == 1


def test_a_following_bonus_shows_the_change_and_a_lower_one_ends_the_higher():
    index, cal = setup()
    deck = index.decks.decks[1]
    song = next(
        l for l in lines_on(index, cal, d(2023, 6, 9))["start"] if l.has_release
    )
    lower = dataclasses.replace(song, category="end", before=7)
    assert lower.drop and lower.section == "drop"
    assert not song.drop and song.section == "start"
    assert (
        notice_text(lower, deck, index).splitlines()[1]
        == "> 7% -> 5% | June 9 - June 13"
    )

    day = d(2023, 6, 9)
    start = int(datetime(2023, 6, 9, tzinfo=SM.timezone).timestamp())
    embed = notice_embed(
        index, deck, day, {"start": ["> a\n"], "drop": ["> b\n"]}, None
    )
    assert embed.fields[1].name == f"Ends <t:{start}:R> :orange_circle:"


def test_a_list_entry_shows_the_change_but_keeps_its_own_status_text():
    index, cal = setup()
    deck = index.decks.decks[1]
    member, _ = by_kind(entries_of(index, cal, 1))
    today = d(2023, 6, 1)
    down = entry_value(dataclasses.replace(member, before=4), deck, index, today=today)
    assert down.startswith("4% -> 2% | June 9 - June 15 | ")
    assert "Available <t:" in down and "Ends" not in down
    active = entry_value(
        dataclasses.replace(member, before=4), deck, index, today=d(2023, 6, 10)
    )
    assert active.startswith("4% -> 2% | ") and "Ends <t:" in active
    up = entry_value(dataclasses.replace(member, before=1), deck, index, today=today)
    assert up.startswith("1% -> 2% | ") and "Available <t:" in up


def test_a_member_from_another_deck_is_followed_by_their_deck():
    t = Tables()
    t.group(1, "TW_ICE")
    t.group(2, "Other")
    t.artist(1, "Guest", 2, birthday=(1999, 6, 12))
    t.artist(2, "Own", 1, birthday=(1999, 6, 12))
    t.song(1, "On Both", 1, release=(2030, 1, 1), artists=[1, 2])
    t.song(2, "Own Only", 1, release=(2030, 1, 1), artists=[2])
    t.song(3, "Other Song", 2, release=(2030, 1, 1), artists=[1])
    tables = t.as_tables()
    index = build_index(SM, tables)
    songs = build_song_periods(index.decks, index.artists, index.locale, [2023])
    cal = BonusCalendar.build(songs)
    deck = index.decks.decks[1]
    today = d(2023, 6, 12)
    names = {
        entry_name(e, deck, index, today)
        for e in entries_of(index, cal, 1)
        if not e.has_release
    }
    assert ":white_check_mark: Guest (from Other) + Own: On Both :birthday:" in names
    # In the guest's own deck they are not a guest.
    (other,) = entries_of(index, cal, 2)
    assert entry_name(other, index.decks.decks[2], index, today).startswith(
        ":white_check_mark: Guest: "
    )
