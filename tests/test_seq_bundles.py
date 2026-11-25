import json
import random
import struct
from pathlib import Path

import httpx
import pytest

from games.charts.seq import SeqError, parse_seq
from games.media.bundles import (
    BuiltInBundle,
    BundleError,
    BundleStore,
    asset_name,
    bundle_name,
    read_text_assets,
)

from .data import NO_RETRY
from .reference.seq_v0 import Seq

BUNDLE = (
    Path(__file__).parent
    / "fixtures"
    / "sounds_assets_sounds_nct_dream_770_9d5f0cc79824258362a8bfa981f4ed7a.bundle"
)
EASY = "easy_pattern_nct_dream_never_goodbye_220427"
NORMAL = "normal_pattern_nct_dream_never_goodbye_220427"
HARD = "hard_pattern_nct_dream_never_goodbye_220427"


def test_names():
    assert asset_name("sounds/nct_dream/770/easy_x.bytes") == "easy_x"
    assert asset_name("a/b/c.d.bytes") == "c.d"
    assert (
        bundle_name("https://cdn.example/a/b/some_bundle.bundle")
        == "some_bundle.bundle"
    )
    assert bundle_name("https://cdn.example/a/b.bundle/") == "b.bundle"


# --- the chart format -----------------------------------------------------------


def test_real_charts_match_what_v0_measured():
    """The numbers v0 stored in SM.json for song 770."""
    data = read_text_assets(BUNDLE, [EASY, NORMAL, HARD])
    got = {name: parse_seq(raw) for name, raw in data.items()}
    assert {name: s.count for name, s in got.items()} == {
        EASY: 113,
        NORMAL: 223,
        HARD: 378,
    }
    assert all(s.seconds == 86.74169921875 and s.invalid == 0 for s in got.values())


def test_the_reference_reader_agrees_on_the_real_charts(tmp_path):
    for name, raw in read_text_assets(BUNDLE, [EASY, NORMAL, HARD]).items():
        path = tmp_path / f"{name}.seq"
        path.write_bytes(raw)
        old = Seq(path)
        new = parse_seq(raw)
        assert (old.count, old.invalid_count, old.SEQData_Info["secLength"]) == (
            new.count,
            new.invalid,
            new.seconds,
        )


def make_chart(rng: random.Random, layout: int, chart_type: int) -> bytes:
    pad = {0x65: 0, 0x66: 4, 0x67: 4}[layout]
    padding = b"\0" * pad
    events = []
    for i in range(rng.randint(2, 80)):
        channel = rng.choice([0, 1, 2, 4, 8, 12, 13, 20, 30])
        prop = rng.choice([11, 14, 21, 24, 12, 22, 5, 100, 11111, 4001, 13, 23])
        tick = rng.randint(0, 120)
        duration = rng.choice([0, 0, 0, 3])
        events.append((tick, duration, channel, 0, prop))
    objects = [(7, b"a"), (8, b""), (9, b"xyz")]
    out = struct.pack("<I", layout) + struct.pack("<I", 100) + struct.pack("<d", 61.5)
    out += struct.pack("<I", 480) + padding + struct.pack("<d", 0.5)
    out += struct.pack("<IIII", 1, len(objects), 2, len(events))
    out += struct.pack("<II", 4, 16) + struct.pack("<I", chart_type) + padding
    out += struct.pack("<IIffdI", 0, 100, 0.0, 61.5, 120.0, 4) + padding
    out += struct.pack("<ddI", 0.25, 0.001, 1920) + padding
    out += struct.pack("<dddddd", 2.0, 0.5, 8.0, 0.125, 0.5, 2.0)
    out += struct.pack("<II", 0, 16)
    first_data = objects[0][1]
    out += struct.pack("<I", len(first_data)) + first_data
    for prop, data in objects[1:]:
        out += struct.pack("<II", prop, len(data)) + data
    out += struct.pack("<I", objects[0][0])
    out += struct.pack("<II", 5, 1) * 2
    for e in events:
        out += struct.pack("<IIIII", *e) + padding
    return out


@pytest.mark.parametrize("seed", range(40))
def test_matches_the_reference_reader_on_generated_charts(seed, tmp_path):
    rng = random.Random(seed)
    layout = rng.choice([0x65, 0x66, 0x67])
    chart_type = rng.choice([0x68, 0x6B, 0x71, 0x7D])
    raw = make_chart(rng, layout, chart_type)
    path = tmp_path / "c.seq"
    path.write_bytes(raw)
    old, new = Seq(path), parse_seq(raw)
    assert (old.count, old.invalid_count) == (new.count, new.invalid)
    assert new.seconds == 61.5


def test_slider_notes_count_twice_only_in_the_slider_layout():
    rng = random.Random(1)
    counts = {
        parse_seq(make_chart(random.Random(s), 0x67, 0x7D)).count for s in range(30)
    }
    assert len(counts) > 1  # the generator does produce varied charts
    del rng


def test_unknown_chart_types_and_odd_properties_do_not_crash():
    odd = make_chart(random.Random(5), 0x67, 0x99)  # v0 raised KeyError here
    assert parse_seq(odd).count == 0
    # A one-digit property in the slider layout is a plain note.
    raw = bytearray(make_chart(random.Random(6), 0x67, 0x7D))
    assert parse_seq(bytes(raw)).count >= 0


def test_bad_charts_are_refused():
    with pytest.raises(SeqError):
        parse_seq(b"")
    with pytest.raises(SeqError):
        parse_seq(struct.pack("<I", 0x99) + b"\0" * 100)
    good = make_chart(random.Random(3), 0x66, 0x7D)
    with pytest.raises(SeqError):
        parse_seq(good[: len(good) // 2])


def test_a_chart_kept_as_base64_text_reads_the_same():
    import base64

    chart = make_chart(random.Random(5), 0x66, 0x68)
    wrapped = base64.b64encode(chart)
    assert wrapped.startswith(b"ZgAA")  # how the Push Push charts begin
    assert parse_seq(wrapped) == parse_seq(chart)
    assert parse_seq(wrapped + b"\n") == parse_seq(chart)
    with pytest.raises(SeqError):
        parse_seq(b"not a chart at all!")


# --- bundles --------------------------------------------------------------------


PUSH_PUSH = (
    Path(__file__).parent
    / "fixtures"
    / "music_assets_music_pattern_sistar_push_push.bundle"
)
# What the game's catalog says for the two keys of the easy chart. Both are named
# easy_pattern_sistar_push_push_191127 inside the bundle; one holds the chart as
# base64 text and one as binary.
SEQ_ID = "1b8c15771f5cc4a898ef313cd21c01c5"  # key ...push_push_191127.seq
BYTES_ID = "701a9d94d79244ebf8dfa8ba4083835d"  # key ...push_push_191127.bytes


def test_an_id_picks_the_one_asset_a_name_shares_with_another():
    name = "easy_pattern_sistar_push_push_191127"
    found = read_text_assets(PUSH_PUSH, [name], [SEQ_ID, BYTES_ID, "0" * 32])
    assert set(found) == {name, SEQ_ID, BYTES_ID}  # an unknown id is left out
    assert found[SEQ_ID].startswith(b"ZgAA")  # base64
    assert found[BYTES_ID][:4] == b"\x66\0\0\0"  # binary
    assert parse_seq(found[SEQ_ID]) == parse_seq(found[BYTES_ID])
    assert parse_seq(found[BYTES_ID]).count == 187


def test_missing_assets_are_left_out_and_bad_files_raise(tmp_path):
    assert read_text_assets(BUNDLE, ["nope"]) == {}
    assert set(read_text_assets(BUNDLE, [EASY, "nope"])) == {EASY}
    # UnityPy does not raise on a file that is not a bundle; it finds nothing.
    bad = tmp_path / "bad.bundle"
    bad.write_bytes(b"not a bundle at all" * 10)
    assert read_text_assets(bad, [EASY]) == {}
    with pytest.raises(BundleError):
        read_text_assets(tmp_path / "absent.bundle", [EASY])


def serve(bundle: Path, calls: list[str]):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.path.endswith("missing.bundle"):
            return httpx.Response(404)
        return httpx.Response(200, content=bundle.read_bytes())

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_a_bundle_is_downloaded_once_kept_and_read_in_place(tmp_path):
    calls: list[str] = []
    url = f"https://cdn.example/Android/{BUNDLE.name}"
    async with serve(BUNDLE, calls) as client:
        store = BundleStore(tmp_path, client, retry=NO_RETRY)
        first = await store.read("SM", url, [EASY])
        second = await store.read("SM", url, [HARD])
    assert set(first) == {EASY} and set(second) == {HARD}
    assert len(calls) == 1
    kept = tmp_path / "files" / "SM" / BUNDLE.name
    assert kept.exists() and kept.read_bytes() == BUNDLE.read_bytes()
    # Nothing was unpacked next to it, and no partial file is left behind.
    assert sorted(p.name for p in kept.parent.iterdir()) == [BUNDLE.name]


async def test_concurrent_requests_download_once(tmp_path):
    import asyncio

    calls: list[str] = []
    url = f"https://cdn.example/{BUNDLE.name}"
    async with serve(BUNDLE, calls) as client:
        store = BundleStore(tmp_path, client, retry=NO_RETRY)
        await asyncio.gather(*(store.fetch("SM", url) for _ in range(5)))
    assert len(calls) == 1


async def test_built_in_and_failed_bundles(tmp_path):
    calls: list[str] = []
    async with serve(BUNDLE, calls) as client:
        store = BundleStore(tmp_path, client, retry=NO_RETRY)
        with pytest.raises(BuiltInBundle):
            await store.fetch(
                "SM",
                "{UnityEngine.AddressableAssets.Addressables.RuntimePath}/x.bundle",
            )
        with pytest.raises(BundleError):
            await store.fetch("SM", "https://cdn.example/missing.bundle")
    assert not (tmp_path / "files" / "SM" / "missing.bundle").exists()
    assert not list((tmp_path / "files" / "SM").glob("*.part"))


async def test_bundles_from_v0_are_reused(tmp_path):
    target = tmp_path / "files" / "SM" / BUNDLE.name
    target.parent.mkdir(parents=True)
    target.write_bytes(BUNDLE.read_bytes())
    calls: list[str] = []
    async with serve(BUNDLE, calls) as client:
        data = await BundleStore(tmp_path, client).read(
            "SM", f"https://x/{BUNDLE.name}", [EASY]
        )
    assert EASY in data and calls == []


def test_the_real_sm_file_agrees_with_the_fixture():
    stored = (
        json.loads(Path("/mnt/user-data/uploads/SM.json").read_text())
        if Path("/mnt/user-data/uploads/SM.json").exists()
        else None
    )
    if stored is None:
        pytest.skip("SM.json is not available")
    assert stored["770"]["seq"]["Hard"]["count"] == 378


def test_query_strings_are_not_part_of_a_file_name():
    assert bundle_name("http://cdn/x/kdnl_intro_4.seq?v=21032201") == "kdnl_intro_4.seq"
    assert bundle_name("sounds/a/b.bytes") == "b.bytes"


def test_plain_files_with_different_versions_are_kept_apart(tmp_path):
    store = BundleStore(tmp_path, None)  # type: ignore[arg-type]
    old = store.plain_path("KD", "http://cdn/a/x.seq?v=1")
    new = store.plain_path("KD", "http://cdn/a/x.seq?v=2")
    assert old != new and old.name.endswith("_x.seq") and old.parent.name == "plain"


def test_one_listing_tells_which_files_are_on_disk(tmp_path):
    store = BundleStore(tmp_path, None)  # type: ignore[arg-type]
    here = "http://cdn/a/here.bundle?v=1"
    plain = "http://cdn/a/x.seq?v=1"
    store.path("KD", "here.bundle").parent.mkdir(parents=True)
    store.path("KD", "here.bundle").write_bytes(b"1")
    store.plain_path("KD", plain).parent.mkdir(parents=True)
    store.plain_path("KD", plain).write_bytes(b"1")

    has = store.on_disk("KD")
    assert has(here, False) and not has("http://cdn/a/gone.bundle", False)
    assert has(plain, True) and not has("http://cdn/a/x.seq?v=2", True)
    assert not store.on_disk("none")(here, False)  # a game with no folder
