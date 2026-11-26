from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest

from games.data import catalogs
from games.data.catalog import CatalogError
from games.data.catalogs import addressables_version, sync_catalog
from games.data.storage import DataStore
from games.errors import DataSyncError
from games.media.apks import SETTINGS_MEMBER, ApkStore
from games.registry import GAMES
from games.service import DataService, State
from tests.data import FIXTURES, NO_RETRY
from tests.fakes import FakePlay, Server, make_apk

SETTINGS = (FIXTURES / "settings.json").read_bytes()
SM = GAMES["SM"]
URL = "https://ssm-cdn.dalcomsoft.net/assets/LIVE/Android/2.9.1/catalog_{version}.bin"


def test_the_addressables_version_is_read_from_the_settings():
    assert addressables_version(SETTINGS) == "2.9.1"
    assert addressables_version(b'{"m_AddressablesVersion": "2.7.4"}') == "2.7.4"


@pytest.mark.parametrize(
    "settings",
    [
        b"not json",
        b"[]",
        b"{}",
        b'{"m_AddressablesVersion": ""}',
        b'{"m_AddressablesVersion": 2}',
    ],
)
def test_settings_without_a_version_are_refused(settings):
    with pytest.raises(CatalogError):
        addressables_version(settings)


def test_a_catalog_url_needs_both_slots():
    assert "{addressables}" in SM.catalog_url
    with pytest.raises(ValueError, match="slots"):
        replace(SM, catalog_url="https://cdn/Android/2.7.4/catalog_{version}.bin")
    with pytest.raises(ValueError, match="slots"):
        replace(SM, catalog_url="https://cdn/Android/{addressables}/catalog.bin")


class Catalog:
    pass


async def test_the_catalog_url_has_the_addressables_version_in_it(
    tmp_path, monkeypatch
):
    seen = []

    def handler(request):
        seen.append(str(request.url))
        if request.url.path.endswith("catalog_7.bin"):
            return httpx.Response(404)  # not there: the version before is used
        return httpx.Response(200, content=b"catalog")

    async def load(data):
        return Catalog()

    monkeypatch.setattr(catalogs, "load_catalog", load)
    store = DataStore(tmp_path)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        loaded = await sync_catalog(
            client, SM, store, "7", retry=NO_RETRY, addressables="2.9.1"
        )
        assert (loaded.requested, loaded.effective) == ("7", "6")
        assert seen == [URL.format(version=7), URL.format(version=6)]
        # A kept catalog is used without knowing the version.
        again = await sync_catalog(client, SM, store, "7", retry=NO_RETRY)
        assert again.effective == "6"
        assert len(seen) == 2
        # A download needs it.
        with pytest.raises(DataSyncError, match="Addressables version"):
            await sync_catalog(client, SM, store, "8", retry=NO_RETRY)
        # A game with no catalog URL cannot download one.
        bare = replace(SM, catalog_url=None)
        with pytest.raises(DataSyncError, match="no catalog URL"):
            await sync_catalog(
                client, bare, store, "9", retry=NO_RETRY, addressables="2.9.1"
            )


async def test_newest_file_follows_the_newest_apk(tmp_path):
    folder = tmp_path / "apks" / "SM"
    folder.mkdir(parents=True)
    old = folder / "2.7.3.apk"
    old.write_bytes(make_apk({SETTINGS_MEMBER: b"old"}))
    play = FakePlay(version="2.7.4")
    server = Server(make_apk({SETTINGS_MEMBER: b"new"}))
    now = [0.0]
    async with server.client() as client:
        store = ApkStore(tmp_path, client, play, retry=NO_RETRY, clock=lambda: now[0])
        # The kept APK is old, but Google Play has a newer one: that is read.
        assert await store.newest_file("SM", SETTINGS_MEMBER) == ("2.7.4.apk", b"new")
        calls = len(play.calls)
        assert await store.newest_file("SM", SETTINGS_MEMBER) == ("2.7.4.apk", b"new")
        assert len(play.calls) == calls  # Google Play is not asked again at once
        now[0] += 3601
        await store.newest_file("SM", SETTINGS_MEMBER)
        assert len(play.calls) > calls  # but is, an hour later
        assert (await store.newest_file("SM", "assets/aa/nothing")) is None


async def test_newest_file_without_google_play_uses_what_is_kept(tmp_path):
    folder = tmp_path / "apks" / "SM"
    folder.mkdir(parents=True)
    (folder / "2.7.3.apk").write_bytes(make_apk({SETTINGS_MEMBER: b"kept"}))
    async with Server(b"").client() as client:
        store = ApkStore(tmp_path, client, None, retry=NO_RETRY)
        assert await store.newest_file("SM", SETTINGS_MEMBER) == ("2.7.3.apk", b"kept")
        assert await store.newest_file("BL", SETTINGS_MEMBER) is None  # none kept


class FakeApks:
    def __init__(self, found):
        self.found = found
        self.asked = []

    async def newest_file(self, game, member):
        self.asked.append((game, member))
        return self.found


def make_service(tmp_path, apks):
    return DataService(
        tmp_path,
        client=httpx.AsyncClient(),
        cipher=SimpleNamespace(),
        play=None,
        games=[SM],
        apks=apks,
    )


async def test_the_service_asks_the_apk_and_gives_none_when_it_cannot(tmp_path):
    state = State(SM)
    apks = FakeApks(("2.7.4.apk", SETTINGS))
    service = make_service(tmp_path, apks)
    assert await service._addressables(state) == "2.9.1"
    assert state.addressables == "2.9.1"
    assert apks.asked == [("SM", SETTINGS_MEMBER)]
    apks.found = ("2.7.4.apk", b"{}")  # an APK whose settings do not say
    assert await service._addressables(state) is None
    apks.found = None  # no APK at all
    assert await service._addressables(state) is None
    assert await make_service(tmp_path, None)._addressables(state) is None
    await service._client.aclose()
