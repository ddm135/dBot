from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image as PILImage

import games.images as images_module
from games.bundles import BuiltInBundle, BundleError
from games.images import ImageService, Picture, PrefetchResult, read_images
from games.index import Indexes
from ui.images import files, prepare

from .data import Tables
from .test_index_search import FakeService
from .test_seq_bundles import BUNDLE


def png(color="red") -> PILImage.Image:
    return PILImage.new("RGB", (4, 4), color)


class FakeObject:
    def __init__(self, kind, name, image=None, path_id=0, container=()):
        self.type = SimpleNamespace(name=kind)
        self.path_id = path_id
        self._asset = SimpleNamespace(
            m_Name=name, image=image, m_Container=list(container)
        )

    def read(self):
        return self._asset

    def peek_name(self):
        return self._asset.m_Name


def fake_unitypy(monkeypatch, objects):
    import UnityPy

    monkeypatch.setattr(UnityPy, "load", lambda path: SimpleNamespace(objects=objects))


def test_an_id_picks_the_one_image_among_several_of_one_name(monkeypatch):
    # A border updated under a new dated path: two images, one name.
    pointing_at = lambda path_id: SimpleNamespace(
        asset=SimpleNamespace(m_PathID=path_id)
    )
    fake_unitypy(
        monkeypatch,
        [
            FakeObject("Texture2D", "frame", png("red"), path_id=1),
            FakeObject("Texture2D", "frame", png("blue"), path_id=2),
            FakeObject(
                "AssetBundle",
                "bundle",
                container=[("old-id", pointing_at(1)), ("new-id", pointing_at(2))],
            ),
        ],
    )
    from PIL import Image as PILImage

    def colour(data):
        return PILImage.open(BytesIO(data)).getpixel((0, 0))

    by_id = read_images(BUNDLE, {"frame"}, ["new-id", "old-id", "nope"])
    assert set(by_id) == {"frame", "new-id", "old-id"}
    assert colour(by_id["old-id"]) == (255, 0, 0)  # exactly the one asked for
    assert colour(by_id["new-id"]) == (0, 0, 255)


# --- reading images from a bundle ---------------------------------------------


def test_textures_are_decoded_to_png_and_other_assets_ignored(monkeypatch):
    fake_unitypy(
        monkeypatch,
        [
            FakeObject("Texture2D", "album_a", png("red")),
            FakeObject("Texture2D", "album_b", png("blue")),
            FakeObject("TextAsset", "album_a"),
            FakeObject("Texture2D", "other", png()),
        ],
    )
    found = read_images(BUNDLE, {"album_a", "missing"})
    assert set(found) == {"album_a"}
    decoded = PILImage.open(BytesIO(found["album_a"]))
    assert decoded.format == "PNG" and decoded.getpixel((0, 0)) == (255, 0, 0)


def test_a_texture_wins_over_a_sprite_of_the_same_name(monkeypatch):
    fake_unitypy(
        monkeypatch,
        [
            FakeObject("Sprite", "x", png("green")),
            FakeObject("Texture2D", "x", png("red")),
            FakeObject("Sprite", "x", png("blue")),
        ],
    )
    pixel = PILImage.open(BytesIO(read_images(BUNDLE, {"x"})["x"])).getpixel((0, 0))
    assert pixel == (255, 0, 0)
    fake_unitypy(monkeypatch, [FakeObject("Sprite", "y", png("green"))])
    assert "y" in read_images(BUNDLE, {"y"})  # a sprite alone is enough


def test_an_undecodable_texture_does_not_hide_the_others(monkeypatch):
    class Broken:
        @property
        def image(self):
            raise ValueError("bad texture")

    broken = FakeObject("Texture2D", "bad")
    broken._asset = SimpleNamespace(
        m_Name="bad", image=Broken().image if False else None
    )
    broken._asset = type(
        "A", (), {"m_Name": "bad", "image": property(lambda s: Broken().image)}
    )()
    fake_unitypy(monkeypatch, [broken, FakeObject("Texture2D", "good", png())])
    assert set(read_images(BUNDLE, {"bad", "good"})) == {"good"}


def test_missing_files_raise(tmp_path):
    with pytest.raises(BundleError):
        read_images(tmp_path / "absent.bundle", {"x"})


def test_the_real_sound_bundle_has_no_images():
    assert read_images(BUNDLE, {"easy_pattern_nct_dream_never_goodbye_220427"}) == {}


# --- the service -------------------------------------------------------------------


class FakeBundles:
    def __init__(self):
        self.fetched = []
        self.error = None

    async def open(self, game, url):
        return await self.fetch(game, url)

    async def fetch(self, game, url, *, plain=False):
        self.fetched.append(url)
        if not url.startswith("http"):
            raise BuiltInBundle(url)
        if self.error:
            raise self.error
        return BUNDLE


def world():
    t = Tables()
    t.group(1, "TWICE", emblemImage="emblems/twice.png")
    t.group(2, "BTS", emblemImage=900)
    t.group(3, "NCT", emblemImage="https://cdn/nct.png")
    t.group(4, "BoA", emblemImage="built-in/boa.png")
    t.song(10, "a", 1, album="albums/a.png")
    t.song(11, "b", 2, album=None)
    t.urls = {"900": {"url": "http://cdn/bts.png"}}
    service = FakeService(t.as_tables())
    for deck in (1, 2, 3, 4):
        t.song(100 + deck, f"s{deck}", deck)
    service.set(t.as_tables())
    service.data.catalog = SimpleNamespace(
        catalog=SimpleNamespace(
            bundle_urls=lambda key: {
                "emblems/twice.png": ["https://cdn/emblems_bundle.bundle"],
                "albums/a.png": ["https://cdn/albums.bundle"],
                "built-in/boa.png": ["{Runtime}/boa.bundle"],
            }[key],
            internal_ids=lambda key: [f"id-of-{key}"],
        )
    )
    return service, Indexes(service)


@pytest.fixture
def patched(monkeypatch):
    calls = []

    def fake_read(path, names, ids=()):
        calls.append(set(names))
        return {n: b"PNGDATA" for n in names}

    monkeypatch.setattr(images_module, "read_images", fake_read)
    return calls


async def test_urls_are_passed_through_and_bundled_images_are_decoded(patched):
    service, indexes = world()
    bundles = FakeBundles()
    images = ImageService(bundles, service, indexes)

    assert await images.emblem("SM", 3) == Picture(url="https://cdn/nct.png")
    assert await images.emblem("SM", 2) == Picture(url="http://cdn/bts.png")
    assert bundles.fetched == []  # no bundle was needed

    emblem = await images.emblem("SM", 1)
    assert emblem == Picture(data=b"PNGDATA", filename="twice.png")
    assert patched == [{"twice"}]
    album = await images.album("SM", 10)
    assert album.filename == "a.png"


async def test_nothing_is_returned_for_missing_or_unavailable_images(patched):
    service, indexes = world()
    bundles = FakeBundles()
    images = ImageService(bundles, service, indexes)
    assert await images.album("SM", 11) is None  # the song has no album
    assert await images.album("SM", 999) is None  # unknown song
    assert await images.emblem("SM", 999) is None
    assert await images.emblem("SM", 4) is None  # lives in the APK
    bundles.error = BundleError("down")
    assert await images.emblem("SM", 1) is None
    service.data.catalog = None
    assert await images.album("SM", 10) is None
    service.set(None)  # the game has no data at all
    assert await images.emblem("SM", 3) is None


async def test_results_are_cached_and_the_cache_is_bounded(patched):
    service, indexes = world()
    bundles = FakeBundles()
    images = ImageService(bundles, service, indexes, cache_size=1)
    await images.emblem("SM", 1)
    await images.emblem("SM", 1)
    assert len(bundles.fetched) == 1
    await images.album("SM", 10)  # evicts the emblem
    await images.emblem("SM", 1)
    assert len(bundles.fetched) == 3


async def test_a_built_in_image_is_remembered_as_missing(patched):
    service, indexes = world()
    bundles = FakeBundles()
    bundles.error = BuiltInBundle("x")
    images = ImageService(bundles, service, indexes)
    assert await images.emblem("SM", 1) is None
    assert await images.emblem("SM", 1) is None
    assert len(bundles.fetched) == 1


# --- attaching ---------------------------------------------------------------------


async def test_prepare_chooses_between_a_url_an_attachment_and_the_fallback():
    assert prepare(None, "fallback", "emblem") == ("fallback", [])
    assert prepare(Picture(url="http://x/y.png"), "fallback", "emblem") == (
        "http://x/y.png",
        [],
    )
    url, uploads = prepare(Picture(data=b"abc", filename="a.png"), None, "album")
    assert url == "attachment://album_a.png"
    assert [u.filename for u in uploads] == ["album_a.png"]
    # Files are rebuilt for every send, because a sent file is consumed.
    first, second = files(uploads)[0], files(uploads)[0]
    assert first is not second and first.filename == "album_a.png"
    first.close()
    second.close()
    assert prepare(Picture(), "fb", "x") == ("fb", [])


async def test_a_failed_lookup_is_retried_after_a_short_time(patched):
    """A miss used to be remembered for ever, so an APK that arrived later never helped."""
    service, indexes = world()
    bundles = FakeBundles()
    bundles.error = BundleError("not yet")
    now = [1000.0]
    images = ImageService(bundles, service, indexes, clock=lambda: now[0])

    assert await images.emblem("SM", 1) is None
    assert await images.emblem("SM", 1) is None  # still cooling down: not asked again
    assert len(bundles.fetched) == 1

    bundles.error = None  # the cause is gone (the APK has been downloaded)
    assert await images.emblem("SM", 1) is None  # cool-down not over yet
    now[0] += 601
    picture = await images.emblem("SM", 1)
    assert picture == Picture(data=b"PNGDATA", filename="twice.png")
    assert await images.emblem("SM", 1) is picture  # and now it is kept
    assert len(bundles.fetched) == 2


async def test_why_a_built_in_image_is_missing_is_logged_once(patched, caplog):
    import logging

    service, indexes = world()
    bundles = FakeBundles()
    now = [0.0]
    images = ImageService(bundles, service, indexes, clock=lambda: now[0])
    with caplog.at_level(logging.WARNING, logger="games.images"):
        for _ in range(3):
            await images.emblem("SM", 4)  # built in, and there is no APK
            now[0] += 1000
    messages = [r.getMessage() for r in caplog.records]
    assert len(messages) == 1 and "built in" in messages[0] and "APK" in messages[0]


# --- keeping the album bundles ---------------------------------------------------


class PrefetchBundles(FakeBundles):
    def __init__(self, root):
        super().__init__()
        self.root = root

    def path(self, game, name):
        return self.root / name

    async def fetch(self, game, url, *, plain=False):
        result = await super().fetch(game, url)
        (self.root / url.rsplit("/", 1)[-1]).write_bytes(b"x")
        return result


def prefetch_world():
    t = Tables()
    t.group(1, "TWICE")
    t.song(10, "a", 1, album="albums/a.png")
    t.song(11, "b", 1, album="albums/b.png")  # the same bundle as a
    t.song(12, "c", 1, album="albums/c.png")
    t.song(13, "d", 1, album="https://cdn/d.png")  # a URL: Discord loads it
    t.song(14, "e", 1, album="built-in/e.png")  # in the APK
    t.song(15, "f", 1, album=None)
    service = FakeService(t.as_tables())
    service.data.catalog = SimpleNamespace(
        catalog=SimpleNamespace(
            bundle_urls=lambda key: {
                "albums/a.png": ["https://cdn/one.bundle"],
                "albums/b.png": ["https://cdn/one.bundle"],
                "albums/c.png": ["https://cdn/two.bundle"],
                "built-in/e.png": ["{Runtime}/e.bundle"],
            }[key],
            internal_ids=lambda key: [],
        )
    )
    return service, Indexes(service)


async def test_every_album_bundle_is_downloaded_once(tmp_path):
    service, indexes = prefetch_world()
    bundles = PrefetchBundles(tmp_path)
    images = ImageService(bundles, service, indexes)

    first = await images.prefetch_albums("SM")
    assert sorted(bundles.fetched) == [
        "https://cdn/one.bundle",
        "https://cdn/two.bundle",
    ]
    assert (first.downloaded, first.kept, first.failed, first.built_in) == (2, 0, 0, 1)
    assert "{Runtime}/e.bundle" not in bundles.fetched  # built in: nothing to download

    second = await images.prefetch_albums("SM")
    assert (second.downloaded, second.kept) == (0, 2)


async def test_a_failed_album_download_is_counted_not_raised(tmp_path):
    service, indexes = prefetch_world()
    bundles = PrefetchBundles(tmp_path)
    bundles.error = BundleError("down")
    result = await ImageService(bundles, service, indexes).prefetch_albums("SM")
    assert (result.downloaded, result.failed) == (0, 2)


async def test_a_game_without_a_catalog_has_nothing_to_keep(tmp_path):
    service, indexes = prefetch_world()
    service.data.catalog = None
    images = ImageService(PrefetchBundles(tmp_path), service, indexes)
    assert await images.prefetch_albums("SM") == PrefetchResult()
