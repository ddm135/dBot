import httpx

from games.bundles import BundleStore, asset_name
from games.song_stats import SongStatsStore
from games.song_sync import (
    catalog_refs,
    collect_refs,
    refresh_duration,
    resolve,
    songs_without_charts,
    sync_seq_stats,
)

from .data import NO_RETRY, MemoryStats
from .test_seq_bundles import BUNDLE, EASY, HARD, NORMAL

BASE = "https://cdn.example/Android/"
KEYS = {
    "Easy": f"sounds/nct_dream/770/{EASY}.bytes",
    "Normal": f"sounds/nct_dream/770/{NORMAL}.bytes",
    "Hard": f"sounds/nct_dream/770/{HARD}.bytes",
}
EXPECTED = {"Easy": 113, "Normal": 223, "Hard": 378}


class FakeCatalog:
    def __init__(self, mapping, ids=None):
        self.mapping = mapping
        self.ids = ids or {}

    def bundle_urls(self, key):
        return self.mapping[key]

    def internal_ids(self, key):
        return self.ids.get(key, [])


def tables(**extra):
    return {
        "MusicData": {
            "770": {
                "code": 770,
                "seqEasy": KEYS["Easy"],
                "seqNormal": KEYS["Normal"],
                "seqHard": KEYS["Hard"],
            },
            "5": {"code": 5, "seqEasy": "", "isHidden": False},
        },
        **extra,
    }


def catalog():
    return FakeCatalog({k: [BASE + BUNDLE.name] for k in KEYS.values()})


class Recorder:
    def __init__(self):
        self.calls = []
        self.saves = 0

    def client(self):
        def handler(request):
            self.calls.append(str(request.url))
            return httpx.Response(200, content=BUNDLE.read_bytes())

        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def save(self):
        self.saves += 1


def test_refs_come_from_the_song_or_from_seqdata():
    refs = collect_refs(tables())
    assert {(r.song, r.level) for r in refs} == {
        ("770", "Easy"),
        ("770", "Normal"),
        ("770", "Hard"),
    }
    with_seqdata = collect_refs(
        tables(
            SeqData={
                "1": {"linkedMusic": 9, "seqLevel": 4, "seqPath": "k"},
                "2": {"seqPath": "x"},
            }
        )
    )
    assert [(r.song, r.level, r.ref) for r in with_seqdata] == [("9", "4", "k")]
    ints = collect_refs({"MusicData": {"1": {"seqEasy": 7, "seqHard": True}}})
    assert [(r.level, r.ref) for r in ints] == [("Easy", 7)]


def test_resolve_catalog_keys_and_url_codes():
    t = tables(URLs={"7": {"url": "https://x/y.seq"}})
    ref = collect_refs(t)[0]
    source = resolve(ref, t, catalog())
    assert (source.url, source.dependency, source.asset) == (
        BASE + BUNDLE.name,
        BUNDLE.name,
        asset_name(ref.ref),
    )
    assert resolve(ref, t, None) is None  # a catalog key needs a catalog
    assert resolve(ref, t, FakeCatalog({})) is None  # not in the catalog
    assert resolve(ref, t, FakeCatalog({ref.ref: [None]})) is None
    (direct,) = collect_refs({"MusicData": {"1": {"seqEasy": 7}}})
    plain = resolve(direct, t, None)
    assert (plain.url, plain.dependency, plain.asset) == ("https://x/y.seq", None, None)
    assert resolve(direct, {"URLs": {}}, None) is None


async def test_charts_are_measured_from_the_bundle_and_match_v0(tmp_path):
    rec = Recorder()
    stored = {}
    async with rec.client() as client:
        store = BundleStore(tmp_path, client, retry=NO_RETRY)
        result = await sync_seq_stats(
            "SM", tables(), catalog(), store, stored, rec.save
        )
    assert (result.updated, result.failed, result.missing) == (3, 0, 0)
    assert len(rec.calls) == 1  # three charts, one bundle, one download
    song = stored["770"]
    assert {k: v["count"] for k, v in song["seq"].items()} == EXPECTED
    assert song["seq"]["Hard"]["duration"] == 86.74169921875
    assert song["seq"]["Hard"]["key"] == KEYS["Hard"]
    assert song["seq"]["Hard"]["dependency"] == BUNDLE.name
    assert song["duration"] == "1:27"
    assert rec.saves >= 1
    assert (tmp_path / "files" / "SM" / BUNDLE.name).exists()  # the bundle is kept


async def test_the_result_is_what_info_reads(tmp_path):
    rec = Recorder()
    stored = {}
    async with rec.client() as client:
        await sync_seq_stats(
            "SM",
            tables(),
            catalog(),
            BundleStore(tmp_path, client, retry=NO_RETRY),
            stored,
            rec.save,
        )
    source = MemoryStats()
    await source.save("SM", stored)
    stat = (await SongStatsStore(source).get("SM"))[770]
    assert stat.duration == "1:27"
    assert stat.notes == EXPECTED


async def test_unchanged_charts_are_not_read_or_downloaded_again(tmp_path):
    rec = Recorder()
    stored = {}
    async with rec.client() as client:
        store = BundleStore(tmp_path, client, retry=NO_RETRY)
        await sync_seq_stats("SM", tables(), catalog(), store, stored, rec.save)
        before = len(rec.calls)
        again = await sync_seq_stats("SM", tables(), catalog(), store, stored, rec.save)
    assert (again.updated, again.unchanged) == (0, 3)
    assert len(rec.calls) == before


async def test_the_bundle_of_a_counted_chart_is_kept_if_it_is_not_on_disk(tmp_path):
    rec = Recorder()
    stored = {}
    async with rec.client() as client:
        first = BundleStore(tmp_path / "one", client, retry=NO_RETRY)
        await sync_seq_stats("SM", tables(), catalog(), first, stored, rec.save)
        calls = len(rec.calls)
        # Counted already, but this store has no bundles: the map is fetched.
        empty = BundleStore(tmp_path / "two", client, retry=NO_RETRY)
        again = await sync_seq_stats("SM", tables(), catalog(), empty, stored, rec.save)
        assert (again.updated, again.unchanged, again.downloaded) == (0, 3, 1)
        assert len(rec.calls) == calls + 1  # one bundle, once
        assert (tmp_path / "two" / "files" / "SM" / BUNDLE.name).exists()
        third = await sync_seq_stats("SM", tables(), catalog(), empty, stored, rec.save)
    assert third.downloaded == 0 and len(rec.calls) == calls + 1  # and not again


async def test_a_changed_key_or_bundle_is_measured_again(tmp_path):
    rec = Recorder()
    stored = {}
    async with rec.client() as client:
        store = BundleStore(tmp_path, client, retry=NO_RETRY)
        await sync_seq_stats("SM", tables(), catalog(), store, stored, rec.save)
        stored["770"]["seq"]["Easy"]["dependency"] = "an_older_bundle.bundle"
        stored["770"]["seq"]["Easy"]["count"] = 1
        again = await sync_seq_stats("SM", tables(), catalog(), store, stored, rec.save)
    assert again.updated == 1
    assert stored["770"]["seq"]["Easy"]["count"] == 113


async def test_other_stored_fields_survive(tmp_path):
    rec = Recorder()
    stored = {"770": {"sound": {"duration": "2:00"}}, "999": {"duration": "3:00"}}
    async with rec.client() as client:
        store = BundleStore(tmp_path, client, retry=NO_RETRY)
        await sync_seq_stats("SM", tables(), catalog(), store, stored, rec.save)
    assert stored["770"]["sound"] == {"duration": "2:00"}
    assert stored["999"] == {"duration": "3:00"}


async def test_built_in_missing_and_unreadable_charts_are_counted(tmp_path):
    rec = Recorder()
    t = tables()
    cat = FakeCatalog(
        {
            KEYS["Easy"]: ["{Runtime}/Android/built_in.bundle"],  # built in
            KEYS["Normal"]: [BASE + BUNDLE.name],
            # Hard is not in the catalog
        }
    )
    t["MusicData"]["770"]["seqNormal"] = "sounds/not/in/the/bundle.bytes"
    cat.mapping["sounds/not/in/the/bundle.bytes"] = [BASE + BUNDLE.name]
    bad: set[str] = set()
    async with rec.client() as client:
        store = BundleStore(tmp_path, client, retry=NO_RETRY)
        stored = {}
        result = await sync_seq_stats(
            "SM", t, cat, store, stored, rec.save, known_bad=bad
        )
        assert (result.updated, result.built_in, result.missing, result.failed) == (
            0,
            1,
            1,
            1,
        )
        assert bad == {"SM:sounds/not/in/the/bundle.bytes"}
        # A chart that failed is not tried (and logged) again.
        again = await sync_seq_stats(
            "SM", t, cat, store, stored, rec.save, known_bad=bad
        )
        assert again.failed == 1 and again.built_in == 1
    assert stored == {}
    assert rec.saves == 0  # nothing to save


async def test_plain_chart_files_are_measured_too(tmp_path):
    from games.bundles import read_text_assets

    raw = read_text_assets(BUNDLE, [HARD])[HARD]

    def handler(request):
        return httpx.Response(200, content=raw)

    t = {
        "MusicData": {"1": {"seqHard": 7}},
        "URLs": {"7": {"url": "https://cdn.example/x/hard.seq"}},
    }
    stored = {}
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        store = BundleStore(tmp_path, client, retry=NO_RETRY)
        result = await sync_seq_stats("KD", t, None, store, stored, Recorder().save)
    assert result.updated == 1
    assert stored["1"]["seq"]["Hard"]["count"] == 378
    assert stored["1"]["seq"]["Hard"]["dependency"] is None
    assert list((tmp_path / "files" / "KD" / "plain").glob("*_hard.seq"))


async def test_progress_is_saved_while_running(tmp_path):
    rec = Recorder()
    songs, mapping = {}, {}
    for i in range(6):
        key = f"sounds/a/{i}/{EASY}.bytes"
        songs[str(i)] = {"seqEasy": key}
        mapping[key] = [f"{BASE}b{i}.bundle"]
    async with rec.client() as client:
        store = BundleStore(tmp_path, client, retry=NO_RETRY)
        result = await sync_seq_stats(
            "SM",
            {"MusicData": songs},
            FakeCatalog(mapping),
            store,
            {},
            rec.save,
            flush_every=2,
            concurrency=2,
        )
    assert result.updated == 6 and rec.saves >= 3


def test_duration_is_the_shortest_chart_rounded():
    song = {"seq": {"Easy": {"duration": 79.4}, "Hard": {"duration": 95.0}}}
    refresh_duration(song)
    assert song["duration"] == "1:19"
    empty = {}
    refresh_duration(empty)
    assert "duration" not in empty


def test_songs_without_charts_are_reported():
    t = {"MusicData": {"1": {}, "2": {"isHidden": True}, "3": {}}}
    assert list(songs_without_charts(t, {"1": {"seq": {"Easy": {}}}})) == ["3"]


async def test_the_task_saves_what_info_reads(tmp_path):
    from types import SimpleNamespace

    from games.registry import GAMES
    from games.service import State
    from games.storage import DataStore
    from games.tables import LoadedTables
    from tasks.song_stats import SongStatsSync

    rec = Recorder()
    data = State(GAMES["SM"])
    data.loaded_tables = LoadedTables(None, tables())
    data.catalog = SimpleNamespace(catalog=catalog())
    async with rec.client() as client:
        database = MemoryStats()
        bot = SimpleNamespace(
            stats=SongStatsStore(database),
            db=SimpleNamespace(song_stats=database),
            settings=SimpleNamespace(preferred=True, data_dir=tmp_path),
            games=SimpleNamespace(store=DataStore(tmp_path)),
            bundles=BundleStore(tmp_path, client, retry=NO_RETRY),
        )
        cog = SongStatsSync(bot)
        assert (await cog.sync_game(data)).updated == 3
        assert (await cog.sync_game(data)).unchanged == 3
        stat = (await bot.stats.get("SM"))[770]
        assert (stat.duration, dict(stat.notes)) == ("1:27", EXPECTED)

        data.loaded_tables = None  # nothing to measure without tables
        assert await cog.sync_game(data) is None
        assert await cog.sync_game(State(GAMES["BL"])) is None  # catalog-only


async def test_a_chart_with_a_new_key_is_measured_again(tmp_path):
    rec = Recorder()
    stored = {}
    async with rec.client() as client:
        store = BundleStore(tmp_path, client, retry=NO_RETRY)
        await sync_seq_stats("SM", tables(), catalog(), store, stored, rec.save)
        stored["770"]["seq"]["Easy"]["key"] = "an/older/key.bytes"
        stored["770"]["seq"]["Easy"]["count"] = 1
        again = await sync_seq_stats("SM", tables(), catalog(), store, stored, rec.save)
    assert again.updated == 1 and stored["770"]["seq"]["Easy"]["count"] == 113


def test_the_first_bundle_of_a_key_is_used():
    t = tables()
    ref = collect_refs(t)[0]
    cat = FakeCatalog({ref.ref: [BASE + "first.bundle", BASE + "second.bundle"]})
    source = resolve(ref, t, cat)
    assert (source.dependency, source.url) == ("first.bundle", BASE + "first.bundle")


def test_urls_stored_in_the_song_are_plain_files():
    t = {"MusicData": {"1": {"seqEasy": "https://cdn.example/p/a.seq?v=3"}}}
    (ref,) = collect_refs(t)
    source = resolve(ref, t, None)
    assert (source.url, source.dependency, source.asset) == (
        "https://cdn.example/p/a.seq?v=3",
        None,
        None,
    )


async def test_songs_are_measured_when_the_bot_starts_not_only_at_the_next_hour(
    tmp_path,
):
    import asyncio
    from types import SimpleNamespace

    from games.registry import GAMES
    from games.service import State
    from games.storage import DataStore
    from games.tables import LoadedTables
    from tasks.song_stats import SongStatsSync

    rec = Recorder()
    data = State(GAMES["SM"])
    data.loaded_tables = LoadedTables(None, tables())
    data.catalog = SimpleNamespace(catalog=catalog())
    ready = asyncio.Event()

    class Games:
        store = DataStore(tmp_path)

        async def wait_until_ready(self):
            await ready.wait()

        def __iter__(self):
            return iter([data])

    async with rec.client() as client:
        database = MemoryStats()
        bot = SimpleNamespace(
            stats=SongStatsStore(database),
            db=SimpleNamespace(song_stats=database),
            settings=SimpleNamespace(preferred=True, data_dir=tmp_path),
            games=Games(),
            bundles=BundleStore(tmp_path, client, retry=NO_RETRY),
        )
        cog = SongStatsSync(bot)
        await cog.cog_load()
        try:
            await asyncio.sleep(0.05)
            assert rec.calls == []  # the first data sync has not finished yet
            ready.set()
            await asyncio.wait_for(cog._startup, 5)
            assert len(rec.calls) == 1  # measured without waiting for :25
            assert (await bot.stats.get("SM"))[770].duration == "1:27"
        finally:
            await cog.cog_unload()


async def test_a_second_run_does_not_overlap_the_first(tmp_path):
    import asyncio
    from types import SimpleNamespace

    from tasks.song_stats import SongStatsSync

    gate = asyncio.Event()
    started = []

    class Games:
        async def wait_until_ready(self):
            pass

        def __iter__(self):
            started.append(1)
            return iter([])

    settings = SimpleNamespace(preferred=True)
    cog = SongStatsSync(SimpleNamespace(games=Games(), settings=settings))
    await cog._running.acquire()  # a run is in progress
    assert await cog.run_all() is False
    assert started == []
    cog._running.release()
    assert await cog.run_all() is True and started == [1]
    gate.set()


class KeyedCatalog(FakeCatalog):
    def keys(self):
        return iter(self.mapping)


async def test_charts_of_a_catalog_only_game_are_found_by_key(tmp_path):
    import re

    pattern = re.compile("bytes_notes_(\\d+)_([a-z]+)")
    mapping = {
        "bytes_notes_770_easy": [BASE + BUNDLE.name],
        "bytes_notes_770_normal": [BASE + BUNDLE.name],
        "bytes_notes_999_hard": [BASE + BUNDLE.name],  # not in the tables
        "Audio_Music_770": [BASE + BUNDLE.name],  # not a chart
        42: [BASE + BUNDLE.name],
    }
    cat = KeyedCatalog(mapping)
    refs = catalog_refs({"MusicData": {"770": {}}}, cat, pattern)
    assert [(r.song, r.level, r.ref) for r in refs] == [
        ("770", "Easy", "bytes_notes_770_easy"),
        ("770", "Normal", "bytes_notes_770_normal"),
    ]

    # The bundle holds sound charts under its own names, so only the sync's
    # bookkeeping is checked here: both charts are looked up and none is lost.
    rec = Recorder()
    stored = {}
    async with rec.client() as client:
        store = BundleStore(tmp_path, client, retry=NO_RETRY)
        result = await sync_seq_stats(
            "BL",
            {"MusicData": {"770": {}}},
            cat,
            store,
            stored,
            rec.save,
            seq_pattern=pattern,
        )
    assert result.updated + result.failed == 2
    assert len(rec.calls) == 1  # one bundle for both charts


async def test_only_the_preferred_instance_measures(tmp_path):
    from types import SimpleNamespace

    from games.registry import GAMES
    from games.service import State
    from games.storage import DataStore
    from games.tables import LoadedTables
    from tasks.song_stats import SongStatsSync

    data = State(GAMES["SM"])
    data.loaded_tables = LoadedTables(None, tables())
    data.catalog = SimpleNamespace(catalog=catalog())
    rec = Recorder()
    async with rec.client() as client:
        database = MemoryStats()
        bot = SimpleNamespace(
            stats=SongStatsStore(database),
            db=SimpleNamespace(song_stats=database),
            settings=SimpleNamespace(preferred=False, data_dir=tmp_path),
            games=SimpleNamespace(
                store=DataStore(tmp_path), __iter__=lambda s: iter([data])
            ),
            bundles=BundleStore(tmp_path, client, retry=NO_RETRY),
        )
        cog = SongStatsSync(bot)
        assert await cog.run_all() is False  # not the preferred instance
        assert rec.calls == [] and database.songs == {}

        bot.settings.preferred = True
        await cog.sync_game(data)
        assert set(database.songs["SM"]) == {"770"}


async def test_sorting_the_charts_does_not_hold_the_event_loop(tmp_path, monkeypatch):
    import threading

    from games import song_sync

    seen = set()
    original = song_sync.resolve

    def resolve_here(ref, tables, catalog):
        seen.add(threading.current_thread())
        return original(ref, tables, catalog)

    monkeypatch.setattr(song_sync, "resolve", resolve_here)
    rec = Recorder()
    async with rec.client() as client:
        store = BundleStore(tmp_path, client, retry=NO_RETRY)
        await sync_seq_stats("SM", tables(), catalog(), store, {}, rec.save)
    assert seen and threading.main_thread() not in seen
