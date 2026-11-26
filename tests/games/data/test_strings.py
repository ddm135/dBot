from types import SimpleNamespace

from games.data.strings import (
    load_strings,
    pick,
    read_key_names,
    read_texts,
    shared_data_key,
    table_key,
)
from games.index import album_titles, group_names, song_names
from games.media.bundles import BuiltInBundle
from games.models import StringsConfig
from games.registry import GAMES
from tasks.strings_sync import StringsSync
from tests.data import FIXTURES

BL_FIXTURES = FIXTURES / "bl"
SHARED = BL_FIXTURES / "ItemName_shared.bundle"
ENGLISH = BL_FIXTURES / "ItemName_en.bundle"
KOREAN = BL_FIXTURES / "ItemName_ko.bundle"
CONFIG = StringsConfig(
    "ItemName", ("en", "ko"), "Album_{code}", "Group_{code}", "Music_{code}"
)
BL = GAMES["BL"]

# The catalog keys name the bundles; their file names are the catalog's business.
URLS = {
    shared_data_key("ItemName"): "https://cdn/shared.bundle",
    table_key("ItemName", "en"): "https://cdn/en.bundle",
    table_key("ItemName", "ko"): "https://cdn/ko.bundle",
}
FILES = {
    "https://cdn/shared.bundle": SHARED,
    "https://cdn/en.bundle": ENGLISH,
    "https://cdn/ko.bundle": KOREAN,
}


class FakeCatalog:
    def __init__(self, urls=URLS):
        self.urls = urls

    def bundle_urls(self, key):
        return [self.urls[key]]  # KeyError for a key it does not have


class FakeBundles:
    def __init__(self, built_in=()):
        self.opened = []
        self.built_in = set(built_in)

    async def open(self, game, url):
        self.opened.append(url)
        if url in self.built_in:
            raise BuiltInBundle(url)
        return FILES[url]


def test_shared_data_gives_key_names_and_tables_give_texts():
    names = read_key_names(SHARED, "ItemName")
    assert read_key_names(SHARED, "Menu") == {}  # another collection
    ident = next(i for i, k in names.items() if k == "Album_1002")
    assert read_texts(ENGLISH, "ItemName_en")[ident] == "QUINTESSENCE"
    assert read_texts(KOREAN, "ItemName_ko")[ident] == "QUINTESSENCE"
    assert read_texts(ENGLISH, "NoSuchTable_en") == {}


async def test_strings_are_found_through_the_catalog():
    bundles = FakeBundles()
    strings = await load_strings("BL", FakeCatalog(), bundles, CONFIG)
    assert bundles.opened == [
        "https://cdn/shared.bundle",
        "https://cdn/en.bundle",
        "https://cdn/ko.bundle",
    ]
    assert strings["Album_1002"] == {"en": "QUINTESSENCE", "ko": "QUINTESSENCE"}
    assert strings["Album_5001"] == {
        "en": "CHA CHA CHA (feat. G-DRAGON)",
        "ko": "차차차 (feat. G-DRAGON)",
    }
    assert pick(strings, "Album_5001", ("ko", "en")) == "차차차 (feat. G-DRAGON)"
    assert pick(strings, "Album_9999", ("en",)) is None


async def test_missing_or_built_in_bundles_give_what_there_is():
    # no shared data: nothing can be named
    without = {k: v for k, v in URLS.items() if "Shared" not in k}
    assert await load_strings("BL", FakeCatalog(without), FakeBundles(), CONFIG) == {}
    # no Korean table: English only
    no_ko = {k: v for k, v in URLS.items() if k != table_key("ItemName", "ko")}
    strings = await load_strings("BL", FakeCatalog(no_ko), FakeBundles(), CONFIG)
    assert strings["Album_1001"] == {"en": "Down to Earth"}
    # a built-in table is skipped
    strings = await load_strings(
        "BL", FakeCatalog(), FakeBundles(built_in={"https://cdn/en.bundle"}), CONFIG
    )
    assert strings["Album_1001"] == {"ko": "Down to Earth"}


def test_album_titles_follow_the_language_order():
    tables = {"AlbumData": {"1001": {}, "1002": {}, "9": {}}}
    strings = {
        "Album_1001": {"en": "A", "ko": "가"},
        "Album_1002": {"ko": "<b>나</b>"},
    }
    # BL lists Korean first, then English: a title falls back down that list.
    assert album_titles(BL, tables, strings) == {"1001": "가", "1002": "나"}
    only_english = {"Album_1001": {"en": "A"}}
    assert album_titles(BL, tables, only_english) == {"1001": "A"}
    assert album_titles(GAMES["SM"], tables, strings) == {}  # no string table


async def test_the_sync_keeps_old_strings_when_nothing_is_read(tmp_path):
    bot = SimpleNamespace(bundles=FakeBundles())
    sync = StringsSync(bot)
    data = SimpleNamespace(
        game=BL, catalog=SimpleNamespace(catalog=FakeCatalog()), strings={}
    )
    assert await sync.run_game(data) is True
    assert data.strings["Album_1002"]["en"] == "QUINTESSENCE"
    first = data.strings
    assert await sync.run_game(data) is False  # unchanged: same object kept
    assert data.strings is first
    data.catalog = SimpleNamespace(catalog=FakeCatalog({}))
    assert await sync.run_game(data) is False  # nothing found: nothing lost
    assert data.strings is first
    data.catalog = None
    assert await sync.run_game(data) is False


async def test_group_names_come_from_the_string_table_over_the_locale():
    strings = await load_strings("BL", FakeCatalog(), FakeBundles(), CONFIG)
    assert strings["Group_3"]["en"] == "MEOVV"
    tables = {"GroupData": {"3": {}, "4": {}, "9": {}}}
    assert group_names(BL, tables, strings) == {"3": "MEOVV", "4": "ALLDAY PROJECT"}
    assert group_names(GAMES["SM"], tables, strings) == {}


async def test_song_titles_come_from_the_string_table():
    strings = await load_strings("BL", FakeCatalog(), FakeBundles(), CONFIG)
    assert strings["Music_4"] == {
        "en": "Reason [Verse 1]",
        "ko": "나는 [Verse 1]",
    }
    tables = {"MusicData": {"4": {}, "5": {}, "99999": {}}}
    names = song_names(BL, tables, strings)
    assert names["4"] == "나는 [Verse 1]"  # BL lists Korean first
    assert "99999" not in names
    assert song_names(GAMES["SM"], tables, strings) == {}
