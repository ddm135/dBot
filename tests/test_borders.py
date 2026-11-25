from types import SimpleNamespace

import discord

from games.borders import border_files
from games.bundles import BundleError
from games.drive import FOLDER_MIME, Drive, StoredFile, fingerprint
from games.images import Picture
from games.registry import GAMES
from tasks import borders as borders_task
from tasks.borders import Borders

BL = GAMES["BL"]
SM = GAMES["SM"]


class FakeCatalog:
    def __init__(self, internal):
        self.internal = internal

    def keys(self):
        return iter([*self.internal, 7])  # a key that is not a string

    def internal_ids(self, key):
        return [None, self.internal[key]]

    def bundle_urls(self, key):
        return ["https://cdn/borders.bundle"]


def test_a_catalog_only_game_lists_borders_by_catalog_key():
    catalog = FakeCatalog(
        {
            "Image_ThemeType_12_R_Large": "Assets/x/Image_ThemeType_12_R_Large.png",
            "Image_ThemeType_12_R_Small": "Assets/x/Image_ThemeType_12_R_Small.png",
            "Image_ThemeType_3_R_Large": "Assets/x/Image_ThemeType_3_R_Large.png",
            "Other": "Assets/x/Other.png",
        }
    )
    themes = {
        "ThemeData": {
            "1": {"themeTypeCode": 12, "limitedType": 1},
            "2": {"themeTypeCode": 3, "limitedType": 2},
        }
    }
    assert border_files(BL, themes, catalog) == {
        "12.png": "Image_ThemeType_12_R_Large",
        "3.png": "Image_ThemeType_3_R_Large",
    }
    assert border_files(BL, {}, catalog) == {}  # no themes known: nothing


def table_world():
    locale = {
        "1": {"enUS": "Summer", "koKR": "여름"},
        "2": {"enUS": "", "koKR": "겨울"},
    }
    return {
        "LocaleData": locale,
        "ThemeTypeData": {
            "0": {"code": 0, "gradeR": "x/none.png"},
            "5": {"code": 5, "gradeR": "borders/Summer_R.png"},
            "6": {"code": 6, "gradeR": "borders/Plain_R.png"},
            "7": {"code": 7, "gradeR": "borders/Winter_R.png"},
            "8": {"code": 8, "gradeR": "borders/Lost_R.png"},
        },
        "ThemeData": {
            "a": {
                "themeTypeCode": 5,
                "limitedType": 1,
                "localeName": 1,
                "nameImageZoom": "zoom",
            },
            "b": {"themeTypeCode": 6, "limitedType": 0, "localeName": 1},
            "c": {"themeTypeCode": 7, "limitedType": 1, "localeName": 2},
        },
    }


def test_a_table_game_lists_the_borders_of_limited_themes_with_english_names():
    found = border_files(SM, table_world(), FakeCatalog({}))
    # Plain (not limited), Winter (no English name) and Lost (no theme) are left out.
    assert found == {
        "5 - Summer.png": "borders/Summer_R_Large.png",
        "5z - Summer.png": "borders/Summer_R_Zoom.png",
    }
    assert border_files(GAMES["KD"], {}, FakeCatalog({})) == {}  # no catalog


class FakeFiles:
    """The ``files()`` resource of the Drive API, over two pages of listings."""

    def __init__(self):
        self.calls = []
        self.folders = [[{"id": "f1", "name": "Other"}], [{"id": "f2", "name": "SM"}]]

    def list(self, q, pageToken, fields):
        self.calls.append(("list", q, pageToken))
        if FOLDER_MIME in q:
            page = int(pageToken or 0)
            token = "1" if page == 0 else ""
            return SimpleNamespace(
                execute=lambda num_retries: {
                    "files": self.folders[page],
                    "nextPageToken": token,
                }
            )
        listing = [
            {"id": "i", "name": "5.png", "appProperties": {"source": "key#id"}},
            {"id": "j", "name": "7.png"},
        ]
        return SimpleNamespace(execute=lambda num_retries: {"files": listing})

    def update(self, fileId, body, fields):
        self.calls.append(("update", fileId, body))
        return SimpleNamespace(
            execute=lambda num_retries: {"id": fileId, "webViewLink": "https://drive/x"}
        )

    def create(self, body, fields, media_body=None):
        self.calls.append(("create", body, media_body is not None))
        return SimpleNamespace(
            execute=lambda num_retries: {"id": "new", "webViewLink": "https://drive/x"}
        )


async def test_drive_finds_folders_across_pages_and_lists_and_uploads():
    files = FakeFiles()
    drive = Drive("root", files)
    assert await drive.game_folder("SM") == "f2"  # on the second page
    assert await drive.game_folder("BL") == "new"  # made
    assert files.calls[-1][1] == {
        "name": "BL",
        "mimeType": FOLDER_MIME,
        "parents": ["root"],
    }
    assert await drive.files("f2") == {
        "5.png": StoredFile("i", "key#id"),
        "7.png": StoredFile("j", None),
    }
    assert await drive.upload("f2", "6.png", b"PNG", "k#1") == "https://drive/x"
    assert files.calls[-1] == (
        "create",
        {"name": "6.png", "parents": ["f2"], "appProperties": {"source": "k#1"}},
        True,
    )
    assert "f2' in parents" in files.calls[-2][1]
    await drive.rename("i", "5 (old).png")
    assert files.calls[-1] == ("update", "i", {"name": "5 (old).png"})


class FakeFolder:
    def __init__(self, have=()):
        # name -> where it came from; None for a file from before that was kept
        self.have = dict.fromkeys(have) if not isinstance(have, dict) else dict(have)
        self.uploads = []
        self.renamed = []

    async def game_folder(self, name):
        return f"folder-{name}"

    async def files(self, folder):
        return {n: StoredFile(f"id-{n}", s) for n, s in self.have.items()}

    async def upload(self, folder, name, data, source=""):
        self.uploads.append((folder, name, data))
        self.have[name] = source
        return f"https://drive/{name}"

    async def rename(self, file_id, name):
        old = file_id.removeprefix("id-")
        self.renamed.append((old, name))
        self.have[name] = self.have.pop(old)


class Channel:
    def __init__(self):
        self.sent = []

    async def send(self, text):
        self.sent.append(text)


class FakeImages:
    def __init__(self, missing=()):
        self.asked = []
        self.missing = set(missing)

    async def from_catalog(self, game, key):
        self.asked.append(key)
        return None if key in self.missing else Picture(data=b"PNG:" + key.encode())


class FakeBundles:
    def __init__(self):
        self.fetched = []

    async def fetch(self, game, url):
        self.fetched.append((game, url))
        if url.endswith("broken.bundle"):
            raise BundleError("down")


def make(monkeypatch, folder, images, channel, bundles=None):
    async def find(bot, channel_id, kind):
        assert kind is discord.TextChannel
        return channel

    monkeypatch.setattr(borders_task, "find_channel", find)
    bot = SimpleNamespace(images=images, bundles=bundles or FakeBundles())
    return Borders(bot, folder)  # type: ignore[arg-type]


def limited(*numbers):
    """ThemeData in which every border number belongs to a limited theme."""
    rows = {str(n): {"themeTypeCode": n, "limitedType": 1} for n in numbers}
    return {"ThemeData": rows}


def data_for(game, catalog, tables=None, strings=None):
    return SimpleNamespace(
        game=game,
        catalog=SimpleNamespace(catalog=catalog) if catalog else None,
        tables=tables or {},
        strings=strings or {},
    )


async def test_only_borders_missing_from_the_folder_are_uploaded_and_announced(
    monkeypatch,
):
    catalog = FakeCatalog(
        {
            "Image_ThemeType_1_R_Large": "a/Image_ThemeType_1_R_Large.png",
            "Image_ThemeType_2_R_Large": "a/Image_ThemeType_2_R_Large.png",
            "Image_ThemeType_3_R_Large": "a/Image_ThemeType_3_R_Large.png",
        }
    )
    folder, images, channel = (
        FakeFolder(have={"1.png"}),
        FakeImages(missing={"Image_ThemeType_3_R_Large"}),
        Channel(),
    )
    cog = make(monkeypatch, folder, images, channel)
    assert (
        await cog.announce(data_for(BL, catalog, limited(1, 2, 3))) == 1
    )  # 1 is there, 3 unreadable
    assert folder.uploads == [
        ("folder-" + BL.name, "2.png", b"PNG:Image_ThemeType_2_R_Large")
    ]
    assert channel.sent == [f"{BL.name}: 2.png\n<https://drive/2.png>"]
    # The upload is the record: another run finds 2.png there and does nothing
    # more for it (3 is still unreadable and is tried again).
    images.asked.clear()
    assert await cog.announce(data_for(BL, catalog, limited(1, 2, 3))) == 0
    assert images.asked == ["Image_ThemeType_3_R_Large"]


async def test_nothing_is_done_without_a_catalog_borders_or_a_channel(monkeypatch):
    folder, images = FakeFolder(), FakeImages()
    cog = make(monkeypatch, folder, images, None)
    assert await cog.announce(data_for(BL, None)) == 0  # no catalog yet
    assert (
        await cog.announce(data_for(BL, FakeCatalog({}), limited(1))) == 0
    )  # no borders
    catalog = FakeCatalog({"Image_ThemeType_1_R_Large": "a/b.png"})
    assert (
        await cog.announce(data_for(BL, catalog, limited(1, 2, 3))) == 0
    )  # channel unreachable
    assert folder.uploads == [] and images.asked == []


async def test_without_google_credentials_nothing_is_announced(tmp_path):
    from config import GoogleSettings

    settings = SimpleNamespace(
        google=GoogleSettings(credentials_file=tmp_path / "missing.json")
    )
    bot = SimpleNamespace(settings=settings, images=FakeImages(), bundles=FakeBundles())
    cog = Borders(bot)  # type: ignore[arg-type]
    catalog = FakeCatalog({"Image_ThemeType_1_R_Large": "a/b.png"})
    assert await cog.announce(data_for(BL, catalog, limited(1, 2, 3))) == 0  # type: ignore[arg-type]


async def test_a_border_republished_under_the_same_name_keeps_the_old_one(
    monkeypatch,
):
    catalog = FakeCatalog({"Image_ThemeType_1_R_Large": "a/b.png"})
    old = "Image_ThemeType_0_R_Large#old"
    now = "Image_ThemeType_1_R_Large#a/b.png"  # what the catalog says it is now
    folder = FakeFolder(have={"1.png": old, "1 (old).png": old, "2.png": None})
    images, channel = FakeImages(), Channel()
    cog = make(monkeypatch, folder, images, channel)
    assert await cog.announce(data_for(BL, catalog, limited(1, 2, 3))) == 1
    assert folder.renamed == [("1.png", "1 (old 2).png")]
    assert [u[1] for u in folder.uploads] == ["1.png"]
    assert folder.have["1.png"] == fingerprint(now)  # short: Drive limits properties
    assert len(fingerprint(now)) + len("source") <= 124
    assert channel.sent[0].startswith(f"{BL.name}: 1.png (updated)")
    # Same source now: nothing more to do. A file with no recorded source is
    # never touched.
    assert await cog.announce(data_for(BL, catalog, limited(1, 2, 3))) == 0
    folder.have = {"1.png": now}  # recorded in full, before sources were shortened
    assert await cog.announce(data_for(BL, catalog, limited(1, 2, 3))) == 0
    folder.have = {"1.png": None}
    assert await cog.announce(data_for(BL, catalog, limited(1, 2, 3))) == 0


def test_the_old_name_keeps_the_number_in_front():
    from tasks.borders import _old_name

    assert _old_name("515 - Ponytail.png", set()) == "515 (old) - Ponytail.png"
    assert _old_name("515 - Ponytail.png", {"515 (old) - Ponytail.png"}) == (
        "515 (old 2) - Ponytail.png"
    )
    assert _old_name("7.png", set()) == "7 (old).png"


BL_THEMES = {
    "ThemeData": {
        "1002": {"themeTypeCode": 1000, "limitedType": 1, "analyticsData": "FRAMELESS"},
        "2002": {"themeTypeCode": 1000, "limitedType": 1, "analyticsData": "FRAMELESS"},
        "1003": {"themeTypeCode": 1003, "limitedType": 1, "analyticsData": "Seed"},
        "4003": {"themeTypeCode": 4003, "limitedType": 1, "analyticsData": "FAMOUS "},
        "4004": {"themeTypeCode": 4004, "limitedType": 0, "analyticsData": "WICKED"},
        "5001": {"themeTypeCode": 5001, "limitedType": 2, "analyticsData": "old"},
    }
}
BL_STRINGS = {
    "Theme_1002": {"ko": "SIGNATURE CARD", "en": "SIGNATURE CARD"},
    "Theme_2002": {"ko": "SIGNATURE", "en": "SIGNATURE"},
    "Theme_4003": {"ko": "FAMOUS", "en": "FAMOUS"},
    "Theme_5001": {"en": "CHA CHA CHA"},
}


def test_bl_borders_are_the_limited_themes_named_from_the_string_table():
    catalog = FakeCatalog(
        {
            "Image_ThemeType_1000_R_Large": "a/1000.png",  # shared, names differ
            "Image_ThemeType_1003_R_Large": "a/1003.png",  # no string: analytics
            "Image_ThemeType_4003_R_Large": "a/4003.png",
            "Image_ThemeType_4004_R_Large": "a/4004.png",  # not limited
            "Image_ThemeType_5001_R_Large": "a/5001.png",  # limited type 2 counts
            "Image_ThemeType_9_R_Large": "a/9.png",  # no theme at all
        }
    )
    assert border_files(BL, BL_THEMES, catalog, BL_STRINGS) == {
        "1000.png": "Image_ThemeType_1000_R_Large",
        "1003 - Seed.png": "Image_ThemeType_1003_R_Large",
        "4003 - FAMOUS.png": "Image_ThemeType_4003_R_Large",
        "5001 - CHA CHA CHA.png": "Image_ThemeType_5001_R_Large",
    }


async def test_borders_kept_by_number_are_renamed_not_uploaded_again(monkeypatch):
    catalog = FakeCatalog({"Image_ThemeType_1003_R_Large": "a/1003.png"})
    folder = FakeFolder(have={"1003.png": None})
    cog = make(monkeypatch, folder, FakeImages(), Channel())
    assert await cog.announce(data_for(BL, catalog, BL_THEMES)) == 0
    assert folder.renamed == [("1003.png", "1003 - Seed.png")]
    assert folder.uploads == []
    assert set(folder.have) == {"1003 - Seed.png"}


async def test_the_bundles_of_all_borders_are_downloaded_whatever_drive_has(
    monkeypatch,
):
    class Catalog(FakeCatalog):
        def bundle_urls(self, key):
            return {
                "Image_ThemeType_1_R_Large": ["https://cdn/a.bundle"],
                "Image_ThemeType_2_R_Large": ["https://cdn/a.bundle", None],
                "Image_ThemeType_3_R_Large": ["https://cdn/broken.bundle"],
                "Image_ThemeType_4_R_Large": ["{Runtime}/built-in.bundle"],
            }[key]

    catalog = Catalog(
        {f"Image_ThemeType_{n}_R_Large": f"a/{n}.png" for n in (1, 2, 3, 4)}
    )
    folder = FakeFolder(
        have={"1.png": None, "2.png": None, "3.png": None, "4.png": None}
    )
    bundles = FakeBundles()
    cog = make(monkeypatch, folder, FakeImages(), Channel(), bundles)
    assert await cog.announce(data_for(BL, catalog, limited(1, 2, 3, 4))) == 0
    # Each once; a failed one does not stop the rest; built-in ones are not fetched.
    assert bundles.fetched == [
        (BL.key, "https://cdn/a.bundle"),
        (BL.key, "https://cdn/broken.bundle"),
    ]


async def test_only_the_preferred_instance_downloads_and_uploads_borders(monkeypatch):
    catalog = FakeCatalog({"Image_ThemeType_1_R_Large": "a/1.png"})
    folder, images, bundles = FakeFolder(), FakeImages(), FakeBundles()
    cog = make(monkeypatch, folder, images, Channel(), bundles)
    data = SimpleNamespace(**vars(data_for(BL, catalog, limited(1))))
    cog.bot.settings = SimpleNamespace(preferred=False)
    cog.bot.games = [data]
    assert await cog.run_all() is False
    assert folder.uploads == [] and bundles.fetched == [] and images.asked == []
    cog.bot.settings.preferred = True
    assert await cog.run_all() is True
    assert [u[1] for u in folder.uploads] == ["1.png"] and bundles.fetched


def test_the_migration_plan_sorts_every_file_in_the_folder():
    from games.drive import StoredFile, fingerprint
    from scripts.migrate_borders import plan

    wanted = {
        "1 - A.png": "k1",
        "2 - B.png": "k2",
        "3 - C.png": "k3",
        "4 - D.png": "k4",
        "5 - E.png": "k5",
        "6 - F.png": "k6",
    }
    sources = {name: f"src-{key}" for name, key in wanted.items()}
    have = {
        "1.png": StoredFile("a", None),  # kept under its number alone
        "2 - B.png": StoredFile("b", sources["2 - B.png"]),  # the old long source
        "3 - C.png": StoredFile("c", fingerprint(sources["3 - C.png"])),  # current
        "4 - D.png": StoredFile("d", "something else"),  # republished
        "5 - E.png": StoredFile("e", None),  # no source
        "4 (old) - D.png": StoredFile("x", None),  # not a border the game has
    }
    result = plan(wanted, sources, have)
    assert result.renames == [("a", "1.png", "1 - A.png")]
    assert [n for _, n, _ in result.to_fingerprint] == ["2 - B.png"]
    assert result.current == 1 and result.republished == ["4 - D.png"]
    assert [n for _, n, _ in result.unknown] == ["1 - A.png", "5 - E.png"]
    assert result.missing == ["6 - F.png"] and result.extra == 1
    assert result.pending == 4
