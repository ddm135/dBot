import json

from games.assets import AssetContext
from games.storage import DataStore

ANSWER = {
    "code": 1000,
    "result": {"version": 7, "context": {"MusicData": {"file": "u", "version": 3}}},
    "invoke": None,
}


async def test_only_the_result_is_stored_with_the_same_formatting(tmp_path):
    store = DataStore(tmp_path)
    await store.write_assets("SM", AssetContext.from_json(ANSWER["result"]))
    text = store.assets_path("SM").read_text(encoding="utf-8")
    assert json.loads(text) == ANSWER["result"]
    assert "code" not in json.loads(text) and "invoke" not in json.loads(text)
    assert text == json.dumps(ANSWER["result"], indent=4, ensure_ascii=False)

    again = await store.read_assets("SM")
    assert again is not None
    assert again.version == "7"
    assert again.table_files()["MusicData"].url == "u"


async def test_an_old_file_with_the_full_answer_is_not_read_so_it_is_fetched_again(
    tmp_path,
):
    store = DataStore(tmp_path)
    path = store.assets_path("SM")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(ANSWER, indent=4), encoding="utf-8")
    assert await store.read_assets("SM") is None


async def test_big_tables_are_trimmed_in_memory_but_not_on_disk(tmp_path):
    store = DataStore(tmp_path)
    full = {
        "1": {"code": 1, "enUS": "A", "koKR": "ㄱ", "deDE": "x", "note": "y"},
    }
    await store.write_table("SM", "LocaleData", full)
    await store.write_table("SM", "URLs", {"7": {"code": 7, "url": "u", "size": 3}})
    assert await store.read_table("SM", "LocaleData") == {
        "1": {"enUS": "A", "koKR": "ㄱ"}
    }
    assert await store.read_table("SM", "URLs") == {"7": {"url": "u"}}
    assert json.loads(store.table_path("SM", "LocaleData").read_text("utf-8")) == full


def test_only_locale_entries_that_something_refers_to_are_kept():
    from games.storage import prune_referenced

    tables = {
        "LocaleData": {"1": {"enUS": "a"}, "2": {"enUS": "b"}, "3": {"enUS": "c"}},
        "MusicData": {"9": {"localeName": 1, "albumName": "7"}},
        "GroupData": {"8": {"localeDisplayGroupName": 3}},
    }
    assert prune_referenced("LocaleData", tables) == {
        "1": {"enUS": "a"},
        "3": {"enUS": "c"},
    }
    assert prune_referenced("LocaleData", {"MusicData": {}}) is None


async def test_the_whole_locale_table_is_read_again_when_what_refers_to_it_changes(
    tmp_path,
):
    from games.models import Game
    from games.registry import GAMES
    from games.tables import _prune_tables

    store = DataStore(tmp_path)
    game: Game = GAMES["SM"]
    await store.write_table(
        game.key, "LocaleData", {"1": {"enUS": "a"}, "2": {"enUS": "b"}}
    )
    # An earlier round kept only code 1; a new song now refers to code 2.
    tables = {
        "LocaleData": {"1": {"enUS": "a"}},
        "MusicData": {"9": {"localeName": 1}, "10": {"localeName": 2}},
    }
    await _prune_tables(store, game, tables, ["MusicData"], loaded=object())  # type: ignore[arg-type]
    assert tables["LocaleData"] == {"1": {"enUS": "a"}, "2": {"enUS": "b"}}
    # Nothing changed: what is held is left alone.
    tables["LocaleData"] = {"1": {"enUS": "a"}}
    await _prune_tables(store, game, tables, [], loaded=object())  # type: ignore[arg-type]
    assert tables["LocaleData"] == {"1": {"enUS": "a"}}


def test_urls_are_kept_only_for_games_that_name_files_by_code():
    from games.song_sync import DIFFICULTY_FIELDS
    from games.storage import REFERENCE_FIELDS, prune_referenced

    assert set(DIFFICULTY_FIELDS.values()) <= set(REFERENCE_FIELDS["URLs"])
    urls = {"5": {"url": "a"}, "6": {"url": "b"}, "7": {"url": "c"}}
    by_code = {
        "URLs": urls,
        "GroupData": {"1": {"emblemImage": 5}},
        "MusicData": {"2": {"seqEasy": 7, "album": "Image_Album_1"}},
    }
    assert prune_referenced("URLs", by_code) == {"5": {"url": "a"}, "7": {"url": "c"}}
    by_key = {  # catalog keys and direct URLs, as BL and the like use
        "URLs": urls,
        "GroupData": {"1": {"emblemImage": "https://cdn/e.png"}},
        "MusicData": {"2": {"seqEasy": "bytes_notes_2_easy", "album": "Image_Album_1"}},
    }
    assert prune_referenced("URLs", by_key) == {}


async def test_a_kept_table_is_good_until_a_table_file_changes(tmp_path):
    store = DataStore(tmp_path)
    await store.write_table("SM", "LocaleData", {"1": {"enUS": "a"}})
    await store.write_table("SM", "MusicData", {"9": {"localeName": 1}})
    assert await store.read_kept("SM", "LocaleData") is None  # nothing kept yet

    await store.write_kept("SM", "LocaleData", {"1": {"enUS": "a"}})
    assert await store.read_kept("SM", "LocaleData") == {"1": {"enUS": "a"}}

    # Any table file changing (what is kept depends on all of them) drops it.
    await store.write_table("SM", "MusicData", {"9": {"localeName": 2}, "10": {}})
    assert await store.read_kept("SM", "LocaleData") is None


async def test_pruning_saves_what_it_kept_for_the_next_start(tmp_path):
    from games.registry import GAMES
    from games.tables import _prune_tables

    store = DataStore(tmp_path)
    game = GAMES["SM"]
    full = {"1": {"enUS": "a"}, "2": {"enUS": "b"}}
    music = {"9": {"localeName": 1}}
    await store.write_table(game.key, "LocaleData", full)
    await store.write_table(game.key, "MusicData", music)

    tables = {"LocaleData": full, "MusicData": music}
    await _prune_tables(store, game, tables, ["LocaleData"], None)
    assert await store.read_kept(game.key, "LocaleData") == {"1": {"enUS": "a"}}

    # A start from the kept copy leaves it as it is, and does not read the file.
    tables = {"LocaleData": {"1": {"enUS": "a"}}, "MusicData": music}
    await _prune_tables(store, game, tables, [], None, saved={"LocaleData"})
    assert tables["LocaleData"] == {"1": {"enUS": "a"}}


def test_the_signature_is_the_same_in_every_run(tmp_path):
    """A set of strings is ordered differently by each process (hash seeds)."""
    import subprocess
    import sys

    (tmp_path / "dalcom" / "SM").mkdir(parents=True)
    (tmp_path / "dalcom" / "SM" / "MusicData.json").write_text("{}")
    code = (
        "import sys;from pathlib import Path;from games.storage import _signature;"
        "print(_signature(Path(sys.argv[1])))"
    )
    seen = {
        subprocess.run(
            [sys.executable, "-c", code, str(tmp_path / "dalcom" / "SM")],
            env={"PYTHONHASHSEED": str(seed), "PATH": ""},
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for seed in (1, 2, 3)
    }
    assert len(seen) == 1
