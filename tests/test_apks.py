import io
import zipfile
from pathlib import Path

import httpx
import pytest

from games.apks import ApkStore, member_name, read_member
from games.bundles import BuiltInBundle, BundleStore
from games.errors import PlayStoreError
from games.song_sync import sync_seq_stats
from games.stores import PlayDetails

from .data import NO_RETRY
from .test_seq_bundles import BUNDLE, EASY, HARD, NORMAL

BUILT_IN = "{UnityEngine.AddressableAssets.Addressables.RuntimePath}/Android/built-in_assets_all.bundle"
MEMBER = "assets/aa/Android/built-in_assets_all.bundle"


def make_apk(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()


class FakePlay:
    def __init__(
        self, version="2.7.4", code=274, url="https://play.example/base_assets.apk"
    ):
        self.details_result = PlayDetails(version, code)
        self.url = url
        self.calls = []
        self.error = None

    async def details(self, package):
        self.calls.append(("details", package))
        if self.error:
            raise self.error
        return self.details_result

    async def split_url(self, package, version_code, split_name):
        self.calls.append(("split", version_code, split_name))
        return self.url


class Server:
    def __init__(self, apk: bytes):
        self.apk = apk
        self.requests = []

    def client(self):
        def handler(request):
            self.requests.append(str(request.url))
            return httpx.Response(200, content=self.apk)

        return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_member_names():
    assert member_name(BUILT_IN) == MEMBER
    assert (
        member_name("{Runtime}/Android/sub/dir/x.bundle")
        == "assets/aa/Android/sub/dir/x.bundle"
    )
    assert member_name("https://cdn/x.bundle") is None
    assert member_name("{Runtime}/Android/") is None


def test_read_member(tmp_path):
    apk = tmp_path / "a.apk"
    apk.write_bytes(make_apk({MEMBER: b"data"}))
    assert read_member(apk, MEMBER) == b"data"
    assert read_member(apk, "assets/aa/Android/other") is None
    bad = tmp_path / "bad.apk"
    bad.write_bytes(b"not a zip")
    assert read_member(bad, MEMBER) is None
    assert read_member(tmp_path / "absent.apk", MEMBER) is None


async def test_a_kept_apk_is_used_without_asking_google_play(tmp_path):
    folder = tmp_path / "apks" / "SM"
    folder.mkdir(parents=True)
    (folder / "2.7.3.apk").write_bytes(make_apk({MEMBER: b"kept"}))
    play = FakePlay()
    server = Server(b"")
    async with server.client() as client:
        store = ApkStore(tmp_path, client, play, retry=NO_RETRY)
        assert await store.read("SM", BUILT_IN) == b"kept"
        assert await store.read("SM", BUILT_IN) == b"kept"  # from memory
    assert play.calls == [] and server.requests == []


async def test_the_apk_is_downloaded_once_kept_and_read_in_memory(tmp_path):
    play = FakePlay()
    server = Server(make_apk({MEMBER: b"fresh", "other": b"x"}))
    async with server.client() as client:
        store = ApkStore(tmp_path, client, play, retry=NO_RETRY)
        assert await store.read("SM", BUILT_IN) == b"fresh"
    assert server.requests == ["https://play.example/base_assets.apk"]
    assert play.calls[0][0] == "details" and play.calls[1][2] == "base_assets"
    kept = tmp_path / "apks" / "SM" / "2.7.4.apk"
    assert kept.exists()
    # The bundle itself was never written out.
    assert (
        not list((tmp_path / "files").glob("**/*"))
        if (tmp_path / "files").exists()
        else True
    )


async def test_a_missing_bundle_does_not_hit_google_play_again_for_an_hour(tmp_path):
    now = [1000.0]
    play = FakePlay()
    server = Server(make_apk({"other": b"x"}))
    async with server.client() as client:
        store = ApkStore(tmp_path, client, play, retry=NO_RETRY, clock=lambda: now[0])
        assert await store.read("SM", BUILT_IN) is None
        first = len(play.calls)
        assert await store.read("SM", BUILT_IN) is None
        assert len(play.calls) == first  # in the cool-down
        now[0] += 3601
        assert await store.read("SM", BUILT_IN) is None
        # A second try finds the version already kept, so it downloads nothing.
        assert len(server.requests) == 1


async def test_a_new_game_version_is_fetched_when_the_old_apk_lacks_the_bundle(
    tmp_path,
):
    folder = tmp_path / "apks" / "SM"
    folder.mkdir(parents=True)
    (folder / "2.7.3.apk").write_bytes(make_apk({"other": b"x"}))
    play = FakePlay(version="2.7.4")
    server = Server(make_apk({MEMBER: b"new"}))
    async with server.client() as client:
        store = ApkStore(tmp_path, client, play, retry=NO_RETRY)
        assert await store.read("SM", BUILT_IN) == b"new"
    assert (folder / "2.7.3.apk").exists() and (
        folder / "2.7.4.apk"
    ).exists()  # old one kept


async def test_google_play_failures_give_none_not_an_error(tmp_path):
    play = FakePlay()
    play.error = PlayStoreError("no token")
    server = Server(b"")
    async with server.client() as client:
        store = ApkStore(tmp_path, client, play, retry=NO_RETRY)
        assert await store.read("SM", BUILT_IN) is None
        assert await ApkStore(tmp_path, client, None).read("SM", BUILT_IN) is None
        assert await store.read("SM", "https://cdn/x.bundle") is None
        assert await store.read("XX", BUILT_IN) is None  # unknown game


async def test_the_memory_cache_is_bounded(tmp_path):
    folder = tmp_path / "apks" / "SM"
    folder.mkdir(parents=True)
    members = {f"assets/aa/Android/b{i}.bundle": bytes(40) for i in range(3)}
    (folder / "2.7.4.apk").write_bytes(make_apk(members))
    async with Server(b"").client() as client:
        store = ApkStore(tmp_path, client, None, cache_bytes=100)
        for i in range(3):
            assert await store.read("SM", f"{{R}}/Android/b{i}.bundle") == bytes(40)
        assert len(store._cache) == 2  # the oldest was dropped
        big = ApkStore(tmp_path, client, None, cache_bytes=10)
        assert await big.read("SM", "{R}/Android/b0.bundle") == bytes(40)
        assert len(big._cache) == 0  # too big to keep, still returned


async def test_charts_in_a_built_in_bundle_are_measured(tmp_path):
    """The APK holds the real sample bundle; its charts are measured in memory."""
    folder = tmp_path / "apks" / "SM"
    folder.mkdir(parents=True)
    (folder / "2.7.4.apk").write_bytes(make_apk({MEMBER: BUNDLE.read_bytes()}))
    tables = {
        "MusicData": {
            "770": {
                "seqEasy": f"sounds/nct_dream/770/{EASY}.bytes",
                "seqNormal": f"sounds/nct_dream/770/{NORMAL}.bytes",
                "seqHard": f"sounds/nct_dream/770/{HARD}.bytes",
            }
        }
    }

    class Catalog:
        def bundle_urls(self, key):
            return [BUILT_IN]

        def internal_ids(self, key):
            return []

    async def save():
        pass

    async with Server(b"").client() as client:
        apks = ApkStore(tmp_path, client, None)
        bundles = BundleStore(tmp_path, client, retry=NO_RETRY, apks=apks)
        stored = {}
        result = await sync_seq_stats("SM", tables, Catalog(), bundles, stored, save)
    assert (result.updated, result.built_in) == (3, 0)
    assert {k: v["count"] for k, v in stored["770"]["seq"].items()} == {
        "Easy": 113,
        "Normal": 223,
        "Hard": 378,
    }
    assert stored["770"]["seq"]["Easy"]["dependency"] == "built-in_assets_all.bundle"
    assert not (tmp_path / "files").exists()  # nothing was written next to the APK


async def test_without_an_apk_built_in_bundles_are_still_reported(tmp_path):
    async with Server(b"").client() as client:
        bundles = BundleStore(tmp_path, client, retry=NO_RETRY)
        with pytest.raises(BuiltInBundle):
            await bundles.open("SM", BUILT_IN)
        store = BundleStore(
            tmp_path, client, retry=NO_RETRY, apks=ApkStore(tmp_path, client, None)
        )
        with pytest.raises(BuiltInBundle):
            await store.read("SM", BUILT_IN, [EASY])
    assert isinstance(Path(tmp_path), Path)


async def test_the_newest_kept_apk_is_searched_first(tmp_path):
    import os

    folder = tmp_path / "apks" / "SM"
    folder.mkdir(parents=True)
    old, new = folder / "2.7.3.apk", folder / "2.7.4.apk"
    old.write_bytes(make_apk({MEMBER: b"old"}))
    new.write_bytes(make_apk({MEMBER: b"new"}))
    os.utime(old, (1_000_000, 1_000_000))
    os.utime(new, (2_000_000, 2_000_000))
    async with Server(b"").client() as client:
        assert await ApkStore(tmp_path, client, None).read("SM", BUILT_IN) == b"new"


def test_needs_apk_looks_for_built_in_files_the_tables_refer_to():
    from games.apks import needs_apk

    class Catalog:
        def bundle_urls(self, key):
            return {"a.png": ["https://cdn/a.bundle"], "b.png": [BUILT_IN]}[key]

    online = {
        "GroupData": {"1": {"emblemImage": "a.png"}},
        "MusicData": {"1": {"album": 5}},
    }
    assert not needs_apk(online, Catalog())
    built_in = {"GroupData": {"1": {"emblemImage": "b.png"}}}
    assert needs_apk(built_in, Catalog())
    assert needs_apk({"MusicData": {"1": {"seqEasy": "b.png"}}}, Catalog())
    # Full URLs, codes, blanks and keys the catalog does not know are not built in.
    other = {
        "MusicData": {
            "1": {"album": "https://x", "image": "", "seqEasy": "unknown.png"}
        }
    }
    assert not needs_apk(other, Catalog())
    assert not needs_apk({}, Catalog())


async def test_prefetch_downloads_only_when_no_apk_is_kept(tmp_path):
    play = FakePlay()
    server = Server(make_apk({MEMBER: b"x"}))
    async with server.client() as client:
        store = ApkStore(tmp_path, client, play, retry=NO_RETRY)
        first = await store.prefetch("SM")
        assert first is not None and first.name == "2.7.4.apk"
        assert len(server.requests) == 1
        again = await store.prefetch("SM")  # one is kept: nothing to do
        assert again == first and len(server.requests) == 1
        assert await ApkStore(tmp_path / "other", client, None).prefetch("SM") is None


async def test_a_failed_prefetch_waits_before_trying_again(tmp_path):
    now = [100.0]
    play = FakePlay()
    play.error = PlayStoreError("down")
    async with Server(b"").client() as client:
        store = ApkStore(tmp_path, client, play, retry=NO_RETRY, clock=lambda: now[0])
        assert await store.prefetch("SM") is None
        calls = len(play.calls)
        assert await store.prefetch("SM") is None
        assert len(play.calls) == calls  # cooling down
        play.error = None
        now[0] += 3601
        server = Server(make_apk({MEMBER: b"x"}))
    async with server.client() as client:
        store._client = client
        assert await store.prefetch("SM") is not None
