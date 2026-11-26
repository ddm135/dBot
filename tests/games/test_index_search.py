import asyncio
from datetime import date, datetime

from games.charts.song_stats import (
    SongStatsStore,
    format_duration,
    parse_duration,
    parse_stats,
)
from games.data.decks import deck_scores, live_theme_maximum, member_counts
from games.index import Indexes, build_index, parse_color
from games.registry import GAMES
from tests.data import MemoryStats, Tables, d, sample
from tests.fakes import FakeService
from ui.search import Search, Searcher, rank
from ui.song import song_embed

SM = GAMES["SM"]


def test_member_counts_skip_type_4():
    t = sample()
    assert member_counts(t.artists) == {1: 2, 2: 1}


def test_deck_scores_use_the_base_score_and_member_count():
    t = sample()
    scores = deck_scores(t.as_tables(), 6_000_000, [1, 2, 3])
    assert scores[1].base == 6_000_000 + 15_000 * (2 - 3)
    assert scores[3].member_count == 0
    assert deck_scores(t.as_tables(), None, [1])[1].base == 0


def test_live_theme_maximum_needs_the_reward_field_and_known_decks():
    t = sample()
    counts = member_counts(t.artists)
    tables = t.as_tables()
    assert live_theme_maximum(tables, counts, {1, 2}) == 0  # no table
    tables["LiveThemeData"] = {
        "1": {"groupID": 1},
        "2": {"groupID": 2},
        "3": {"groupID": 9},
    }
    assert live_theme_maximum(tables, counts, {1, 2}) == 0  # no collectRewardID
    tables["LiveThemeData"] = {
        "1": {"groupID": 1, "collectRewardID": 1},
        "2": {"groupID": 2, "collectRewardID": 2},
        "3": {"groupID": 9, "collectRewardID": 3},
        "4": {"groupID": 1, "collectRewardID": 4},
    }
    assert live_theme_maximum(tables, counts, {1, 2}) == 15_000 * (2 + 1 + 2)
    counts[9] = 4  # a deck that is not in the song data is not counted
    assert live_theme_maximum(tables, counts, {1, 2}) == 15_000 * (2 + 1 + 2)


def test_build_index_resolves_urls_and_colours():
    t = sample()
    index = build_index(SM, t.as_tables())
    assert index.album_color(100) == 0xFF8800
    assert index.album_color(101) is None
    assert parse_color("0x0f0f11FF") == 0x0F0F11  # the format in the game tables
    assert parse_color("FF8800FF") == 0xFF8800 and parse_color("#112233") == 0x112233
    assert parse_color("0xZZZZZZFF") is None and parse_color("0x12") is None
    assert parse_color(None) is None and parse_color(5) is None
    assert index.resolve_url("https://a/b") == "https://a/b"
    assert index.resolve_url("Assets/x.png") is None
    assert index.resolve_url(12345) is None
    assert index.deck_max_score(1) == SM.base_score - 15_000
    assert build_index(SM, {}) is None


def test_indexes_are_cached_until_tables_change():
    tables = sample().as_tables()
    service = FakeService(tables)
    indexes = Indexes(
        service, clock=lambda game: datetime(2025, 6, 1, tzinfo=game.timezone)
    )

    first = indexes.get("SM")
    assert first is indexes.get("SM")
    # A new LoadedTables around the same table objects is not a change.
    service.set(dict(tables))
    assert indexes.get("SM") is first
    # A replaced table is.
    service.set({**tables, "MusicData": dict(tables["MusicData"])})
    assert indexes.get("SM") is not first
    service.set(None)
    assert indexes.get("SM") is None
    assert indexes.current_calendar("SM") is None


def test_calendar_is_built_per_year_and_cached():
    tables = sample().as_tables()
    service = FakeService(tables)
    indexes = Indexes(
        service, clock=lambda game: datetime(2025, 6, 1, tzinfo=game.timezone)
    )
    assert indexes.today(SM) == date(2025, 6, 1)
    cal = indexes.current_calendar("SM")
    assert cal.years == (2025, 2026)
    assert indexes.calendar("SM", 2025) is cal
    assert indexes.calendar("SM", 2026) is not cal
    assert 200 not in cal.songs  # hidden
    assert cal.events_on(d(2025, 9, 19))  # Nayeon's window opens 3 days before 9/22


def test_games_without_a_bonus_sheet_have_no_calendar():
    assert SM.has_bonuses
    assert not GAMES["KD"].has_bonuses
    assert not GAMES["BL"].has_bonuses


# --- search ---------------------------------------------------------------------


def test_rank_order():
    assert rank(["cheer up"], "cheer up") == 0
    assert rank(["cheer up"], "che") == 1
    assert rank(["cheer up"], "up") == 2
    assert rank(["cheer up"], "eer") == 3
    assert rank(["cheer up"], "zzz") is None
    assert rank(["abc", "xyz"], "xyz") == 0


def search_for(aliases=None):
    index = build_index(SM, sample().as_tables())
    return Search(index, aliases or {})


def test_search_matches_any_language_and_ranks_prefixes_first():
    s = search_for()
    assert [h.label for h in s.songs("cheer")] == ["Cheer Up"]
    assert [h.label for h in s.songs("치어")] == ["Cheer Up"]
    assert [h.label for h in s.songs("チア")] == ["Cheer Up"]
    assert [h.code for h in s.songs("100")] == [100]  # by code
    assert [h.label for h in s.decks("tw")] == ["TWICE"]
    assert [h.label for h in s.songs("")] == ["Cheer Up", "Fancy", "Dynamite"]
    assert len(s.songs("", limit=2)) == 2


def test_search_can_be_limited_to_a_deck_and_flags_hidden():
    s = search_for()
    assert {h.deck_code for h in s.songs("", deck_code=1)} == {1}
    (hit,) = s.songs("dyn")
    assert hit.hidden and hit.choice_name == "Dynamite (Hidden)"


def test_aliases_are_searchable():
    s = search_for({("deck", 1): ["nayeon's group"], ("song", 101): ["zzz"]})
    assert [h.code for h in s.decks("nayeon")] == [1]
    assert [h.code for h in s.songs("zzz")] == [101]


def test_choice_names_are_truncated_to_discords_limit():
    from ui.search import Hit

    assert len(Hit(1, "x" * 150).choice_name) == 100


async def test_searcher_applies_alias_changes(database):
    service = FakeService(sample().as_tables())
    indexes = Indexes(service)
    searcher = Searcher(indexes, database.aliases)
    await searcher.load(["SM"])
    assert searcher.game("SM").songs("nickname") == []

    assert await searcher.add_alias("SM", "song", 101, " Nickname ")
    assert not await searcher.add_alias("SM", "song", 101, "nickname")
    assert [h.code for h in searcher.game("SM").songs("nickname")] == [101]
    assert searcher.aliases_of("SM", "song", 101) == ["nickname"]

    # A new searcher sees it after loading from the database.
    other = Searcher(indexes, database.aliases)
    await other.load(["SM"])
    assert [h.code for h in other.game("SM").songs("nickname")] == [101]

    assert await searcher.remove_alias("SM", "song", 101, "NICKNAME")
    assert not await searcher.remove_alias("SM", "song", 101, "nickname")
    assert searcher.game("SM").songs("nickname") == []

    service.set(None)
    assert searcher.game("SM") is None


# --- song stats -----------------------------------------------------------------


def test_duration_helpers():
    assert format_duration(200.4) == "3:20"
    assert format_duration(59.5) == "1:00"
    assert parse_duration("3:21") == 201
    assert parse_duration("x") is None
    assert parse_duration("3-21") is None
    assert parse_duration(None) is None


def test_parse_stats_prefers_the_stored_duration_and_falls_back():
    stats = parse_stats(
        {
            "1": {
                "duration": "3:21",
                "seq": {"Easy": {"count": 100, "duration": 150.0}},
            },
            "2": {
                "seq": {
                    "Easy": {"count": 5, "duration": 120.6},
                    "Hard": {"count": 9, "duration": 121.0},
                }
            },
            "3": {"sound": {"duration": "1:05"}},
            "4": {},
            "bad": {"duration": "1:00"},
            "5": "nope",
        }
    )
    assert stats[1].duration == "3:21" and stats[1].notes == {"Easy": 100}
    assert stats[2].seconds == 121 and stats[2].notes == {"Easy": 5, "Hard": 9}
    assert stats[3].seconds == 65
    assert stats[4].duration == "Unknown"
    assert set(stats) == {1, 2, 3, 4}


async def test_stats_store_reads_caches_and_follows_the_version():
    source = MemoryStats()
    now = [0.0]
    store = SongStatsStore(source, recheck=30, clock=lambda: now[0])
    assert await store.get("SM") == {}
    source.songs["SM"] = {"1": {"duration": "1:00"}}
    source.versions["SM"] = 1
    assert await store.get("SM") == {}  # not looked at again yet
    now[0] += 31
    first = await store.get("SM")
    assert first[1].seconds == 60
    assert await store.get("SM") is first  # cached

    loads = source.loads
    now[0] += 31
    assert await store.get("SM") is first  # same version: nothing read again
    assert source.loads == loads

    source.songs["SM"] = {"1": {"duration": "2:00"}, "2": {"duration": "0:30"}}
    source.versions["SM"] = 2
    now[0] += 31
    assert (await store.get("SM"))[1].seconds == 120

    async def down(game):
        raise ConnectionError("the database is away")

    source.version = down
    now[0] += 31
    assert (await store.get("SM"))[1].seconds == 120  # keeps the last good copy
    assert await SongStatsStore(source).get("SM") == {}  # nothing known yet


def names_world():
    t = Tables()
    t.group(1, "æspa")
    t.group(2, "TVXQ!")
    t.group(3, "SHINee")
    t.group(4, "SHINee")
    t.group(5, "Red Velvet (Hidden)")
    t.locale["9001"] = {
        "enUS": "TVXQ!",
        "koKR": "TVXQ!",
        "jpJP": "東方神起",
        "jaJP": "東方神起",
    }
    t.groups["2"]["localeName"] = 9001
    t.song(1, "a", 1)
    t.song(2, "b", 2)
    t.song(3, "c", 3)
    t.song(4, "d", 4, hidden=True)  # deck 4 only holds a hidden song
    t.song(5, "e", 5)
    return build_index(SM, t.as_tables())


def test_old_sheet_names_find_their_decks():
    from games.index import find_deck_by_name

    index = names_world()

    def code(n):
        return d.code if (d := find_deck_by_name(index, n)) else None

    assert code("aespa") == 1 and code("ÆSPA") == 1  # the ligature folds
    assert code("東方神起") == 2 and code("tvxq!") == 2  # any language
    assert code("SHINee") == 3  # the main deck wins a shared name
    assert code("SHINee (Hidden)") == 4  # the hidden-only deck
    assert code("Red Velvet (Hidden)") == 5  # a deck really named that
    assert code("aespa (Hidden)") == 1  # no hidden deck: the deck itself
    assert code("Nobody") is None and code("Nobody (Hidden)") is None


def test_a_shared_name_prefers_the_main_deck_even_when_it_sorts_later():
    from games.index import find_deck_by_name

    t = Tables()
    t.group(4, "SHINee", secondOrderIndex=1)  # hidden-only, and listed first
    t.group(3, "SHINee", secondOrderIndex=2)
    t.song(3, "c", 3)
    t.song(4, "d", 4, hidden=True)
    index = build_index(SM, t.as_tables())
    assert [d.code for d in index.decks] == [4, 3]
    assert find_deck_by_name(index, "SHINee").code == 3


def test_renamed_decks_are_found_through_aliases():
    from games.index import find_deck_by_name

    index = names_world()
    aliases = {"Old Name": "aespa", "Old Name (Reload)": "SHINee"}
    assert find_deck_by_name(index, "Old Name") is None
    assert find_deck_by_name(index, "Old Name", aliases).code == 1
    assert find_deck_by_name(index, "Old Name (Reload) (Hidden)", aliases).code == 4
    assert find_deck_by_name(index, "a e s p a").code == 1  # spacing is ignored


def test_a_game_can_prefer_another_language_for_names():
    import dataclasses

    t = Tables()
    t.group(2, "TVXQ!")
    t.locale["9001"] = {"enUS": "TVXQ!", "jaJP": "東方神起"}
    t.groups["2"]["localeName"] = 9001
    t.song(1, "a", 2)
    english = build_index(SM, t.as_tables())
    japanese = build_index(
        dataclasses.replace(SM, languages=("jaJP", "enUS")), t.as_tables()
    )
    assert english.decks.decks[2].name == "TVXQ!"
    assert japanese.decks.decks[2].name == "東方神起"
    assert japanese.group_name(2) == "東方神起"


def test_search_finds_a_string_table_name_in_any_language():
    t = Tables()
    t.group(3, "MEOVV")
    t.song(4, "x", 3)
    strings = {
        "Group_3": {"en": "MEOVV", "ko": "미야오"},
        "Music_4": {"en": "Reason", "ko": "나는"},
    }
    index = build_index(GAMES["BL"], t.as_tables(), strings)
    search = Search(index, {})
    assert [h.code for h in search.decks("미야오")] == [3]  # not the shown one
    assert [h.code for h in search.songs("나는")] == [4]
    assert [h.code for h in search.decks("meovv")] == [3]


def test_chosen_names_replace_the_games_own_for_decks_and_songs():
    t = Tables()
    t.group(2, "TVXQ!")
    t.song(1, "a", 2)
    names = {("deck", 2): "M&D", ("song", 1): "Hello"}
    index = build_index(SM, t.as_tables(), None, names)
    assert index.decks.decks[2].name == "M&D"
    assert index.decks.songs[1].name == "Hello"
    search = Search(index, {})
    assert [h.code for h in search.decks("m&d")] == [2]
    assert [h.code for h in search.decks("tvxq")] == [2]  # the old name still works
    from games.index import find_deck_by_name

    assert find_deck_by_name(index, "M&D").code == 2  # and so do old sheets


async def test_warming_builds_off_the_loop_once_and_leaves_the_caches_full():
    import threading

    service = FakeService(sample().as_tables())
    indexes = Indexes(
        service, clock=lambda game: datetime(2025, 6, 1, tzinfo=game.timezone)
    )
    built_in = []
    original = indexes._build_calendar

    def build_calendar(index, years, **kw):
        built_in.append(threading.current_thread())
        return original(index, years, **kw)

    indexes._build_calendar = build_calendar
    await asyncio.gather(indexes.warm("SM"), indexes.warm("SM"))  # one build, not two
    assert len(built_in) == 1 and built_in[0] is not threading.main_thread()
    cal = indexes.current_calendar("SM")  # found ready: nothing is built here
    assert cal is not None and len(built_in) == 1

    await indexes.warm("SM", 2026)  # another year is another calendar
    assert len(built_in) == 2

    service.set(
        dict(service.data.loaded_tables.tables, MusicData={})
    )  # a changed table
    await indexes.warm("SM")
    assert indexes.current_calendar("SM") is not cal


def test_hidden_songs_and_decks_are_marked_where_users_see_them():
    index = build_index(SM, sample().as_tables())
    dynamite = index.decks.songs[200]
    assert dynamite.display_label == "Dynamite (Hidden)"
    assert index.decks.songs[100].display_label == "Cheer Up"
    assert index.decks.decks[2].display_name == "BTS (Hidden)"  # no visible song
    assert index.decks.decks[1].display_name == "TWICE"
    embed = song_embed(index, index.decks.decks[2], dynamite, None, "SSL", None)
    assert embed.title == "BTS (Hidden)"
    assert "Dynamite (Hidden)" in (embed.description or "")
