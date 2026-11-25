from datetime import datetime

from games.bonus.decks import build_deck_index, clean, locale_text, name_key
from games.bonus.schedule import ms_to_date, ms_to_datetime

from .data import KST, Tables, d, ms


def test_clean_strips_rich_text_tags():
    assert clean("<size=20>Hello</size> ") == "Hello"
    assert clean(None) is None


def test_locale_falls_back_to_korean_then_fallback():
    locale = {"1": {"enUS": "", "koKR": "한"}, "2": {"enUS": "", "koKR": ""}}
    assert locale_text(locale, 1) == "한"
    assert locale_text(locale, 2, "fb") == "fb"
    assert locale_text(locale, 99, "fb") == "fb"
    assert locale_text(locale, None) is None


def test_name_key_ignores_case_and_spacing():
    assert name_key("  Super   Junior ") == name_key("super junior")


def test_timestamps_use_korean_dates():
    assert ms_to_date(ms(1987, 7, 1), KST) == d(1987, 7, 1)  # historic DST year
    assert ms_to_date(0, KST) == d(1970, 1, 1)
    assert ms_to_date(None, KST) is None


def test_index_maps_songs_to_decks_and_hidden_flags():
    t = Tables()
    t.group(1, "TWICE", orderIndex=2)
    t.group(2, "BTS", orderIndex=1)
    t.song(10, "Cheer Up", 1)
    t.song(11, "Secret", 1, hidden=True)
    t.song(20, "Dynamite", 2)
    index = build_deck_index(t.as_tables(), KST)

    assert [deck.name for deck in index] == ["BTS", "TWICE"]  # by orderIndex
    assert index.deck_of(10).name == "TWICE"
    assert index.songs[11].is_hidden
    assert [s.code for s in index.decks[1].visible_songs] == [10]
    assert index.deck_of(999) is None


def test_duplicate_deck_names_label_only_hidden_only_decks_with_code():
    t = Tables()
    t.group(5, "SUPER JUNIOR")
    t.group(20700, "SUPER JUNIOR")
    t.song(1, "Sorry Sorry", 5)
    t.song(2, "Hidden", 20700, hidden=True)
    index = build_deck_index(t.as_tables(), KST)

    assert index.decks[5].label == "SUPER JUNIOR"
    assert index.decks[5].is_main
    assert index.decks[20700].label == "SUPER JUNIOR [20700]"
    assert not index.decks[20700].is_main
    assert index.decks[5].same_name_codes == (20700,)


def test_two_main_decks_with_one_name_both_keep_codes():
    t = Tables()
    t.group(1, "Same")
    t.group(2, "Same")
    t.song(1, "a", 1)
    t.song(2, "b", 2)
    index = build_deck_index(t.as_tables(), KST)
    assert {deck.label for deck in index} == {"Same [1]", "Same [2]"}


def test_duplicate_song_names_in_a_deck_get_codes():
    t = Tables()
    t.group(12, "Deck")
    t.song(1303, "Underwater", 12)
    t.song(10049, "underwater ", 12)
    t.song(5, "Other", 12)
    index = build_deck_index(t.as_tables(), KST)
    labels = {s.code: s.label for s in index.songs.values()}
    assert labels == {
        1303: "Underwater [1303]",
        10049: "underwater [10049]",
        5: "Other",
    }
    assert index.songs[1303].same_name_codes == (10049,)


def test_songs_pointing_at_a_missing_deck_still_get_one():
    t = Tables()
    t.song(1, "Lost", 77)
    index = build_deck_index(t.as_tables(), KST)
    deck = index.decks[77]
    assert not deck.in_group_data
    assert deck.name == "Deck 77"
    assert index.songs[1].deck_code == 77


def test_empty_decks_are_listed_only_when_asked():
    t = Tables()
    t.group(1, "Empty")
    t.group(2, "Full")
    t.song(1, "s", 2)
    assert [d_.name for d_ in build_deck_index(t.as_tables(), KST)] == ["Full"]
    assert len(list(build_deck_index(t.as_tables(), KST, include_empty=True))) == 2


def test_missing_tables_give_an_empty_index():
    index = build_deck_index({}, KST)
    assert list(index) == [] and index.songs == {}


def test_artist_codes_parse_from_json_or_list_and_dedupe():
    t = Tables()
    t.group(1, "G")
    t.song(1, "a", 1, artists=[3, 3, 4])
    t.music["2"] = {**t.music["1"], "code": 2, "artistCode": [7, "8", "x"]}
    t.music["3"] = {**t.music["1"], "code": 3, "artistCode": "not json"}
    t.music["4"] = {**t.music["1"], "code": 4, "artistCode": None}
    index = build_deck_index(t.as_tables(), KST)
    assert index.songs[1].artist_codes == (3, 4)
    assert index.songs[2].artist_codes == (7, 8)
    assert index.songs[3].artist_codes == ()
    assert index.songs[4].artist_codes == ()


def test_display_group_only_when_it_differs_from_the_deck_name():
    t = Tables()
    t.group(1, "Deck")
    t.song(1, "a", 1, localeDisplayGroupName=t.text("Deck"))
    t.song(2, "b", 1, localeDisplayGroupName=t.text("Unit"))
    index = build_deck_index(t.as_tables(), KST)
    assert index.songs[1].display_group is None
    assert index.songs[2].display_group == "Unit"


def test_dates_are_read_in_the_games_own_timezone():
    from zoneinfo import ZoneInfo

    from .data import ms

    manila = ZoneInfo("Asia/Manila")
    midnight_in_seoul = ms(2025, 6, 10)
    # The same instant is a different calendar day an hour behind.
    assert ms_to_date(midnight_in_seoul, KST) == d(2025, 6, 10)
    assert ms_to_date(midnight_in_seoul, manila) == d(2025, 6, 9)

    t = Tables()
    t.group(1, "G")
    t.artist(1, "Mem", 1, birthday=(1999, 6, 12))
    t.song(1, "s", 1, release=(2020, 6, 10), artists=[1])
    seoul = build_deck_index(t.as_tables(), KST)
    philippines = build_deck_index(t.as_tables(), manila)
    assert seoul.songs[1].release == d(2020, 6, 10)
    assert philippines.songs[1].release == d(2020, 6, 9)
    assert philippines.timezone is manila


def test_decks_are_ordered_by_second_order_index_then_order_index():
    t = Tables()
    t.group(1, "A", orderIndex=1, secondOrderIndex=3000)
    t.group(2, "B", orderIndex=9, secondOrderIndex=1000)
    t.group(3, "C", orderIndex=5, secondOrderIndex=1000)
    for code, deck in ((1, 1), (2, 2), (3, 3)):
        t.song(code, f"s{code}", deck)
    index = build_deck_index(t.as_tables(), KST)
    assert [deck.name for deck in index] == ["C", "B", "A"]


def test_timestamps_are_read_leniently():
    assert ms_to_datetime(ms(2025, 6, 10), KST) == datetime(2025, 6, 10, tzinfo=KST)
    for junk in (None, "1", True, 1e30, float("nan")):
        assert ms_to_datetime(junk, KST) is None
        assert ms_to_date(junk, KST) is None


def test_album_decks_split_a_group_by_album_and_use_the_album_release():
    t = Tables()
    t.group(1, "Solo", orderIndex=1)
    t.song(10, "A", 1, albumCode=1001, albumName=t.text("First"))
    t.song(11, "B", 1, albumCode=1002, albumName=t.text("Second"))
    t.song(12, "Secret", 1, albumCode=0, hidden=True)
    tables = t.as_tables()
    tables["AlbumData"] = {
        "1001": {"code": 1001, "groupCode": 1, "releaseDate": ms(2023, 4, 25)},
        "1002": {"code": 1002, "groupCode": 1, "releaseDate": ms(2024, 1, 2)},
    }
    index = build_deck_index(tables, KST, album_decks=True)
    assert [d.code for d in index] == [1, 1001, 1002]  # the group, then its albums
    assert index.decks[1001].name == "Solo : First"
    assert [s.code for s in index.decks[1].songs] == [12]
    assert index.songs[11].release == d(2024, 1, 2)
    assert index.songs[10].deck_code == 1001
    # Without the option, albums are ignored.
    plain = build_deck_index(tables, KST)
    assert [d.code for d in plain] == [1]
