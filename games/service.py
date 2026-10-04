"""The game data the bot works with, and the syncing that keeps it current."""

import asyncio
import logging
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from .apks import SETTINGS_MEMBER, ApkStore
from .catalog import CatalogError
from .catalogs import LoadedCatalog, addressables_version, sync_catalog
from .crypto import Cipher
from .errors import ManifestError, ServiceError
from .http import DEFAULT_RETRY, RetryPolicy
from .magic_onion import MagicOnionClient
from .manifest import Manifest, fetch_manifest
from .models import Game
from .registry import GAMES
from .server import Server
from .storage import DataStore, Table
from .stores import PlayStore, StoreInfo, fetch_store_info
from .tables import LoadedTables, sync_tables

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class State:
    game: Game
    store: StoreInfo | None = None
    icon_url: str | None = None
    manifest: Manifest | None = None
    catalog: LoadedCatalog | None = field(default=None, repr=False)
    addressables: str | None = None  # the build's Addressables version, from its APK
    loaded_tables: LoadedTables | None = field(default=None, repr=False)
    strings: Mapping[str, Mapping[str, str]] = field(default_factory=dict, repr=False)

    @property
    def tables(self) -> Mapping[str, Table]:
        return self.loaded_tables.tables if self.loaded_tables else {}


class DataService:
    def __init__(
        self,
        data_dir: Path,
        *,
        client: httpx.AsyncClient,
        cipher: Cipher,
        play: PlayStore | None,
        games: Iterable[Game] | None = None,
        retry: RetryPolicy = DEFAULT_RETRY,
        apks: ApkStore | None = None,
    ) -> None:
        self.store = DataStore(data_dir)
        self._apks = apks
        self._client = client
        self._cipher = cipher
        self._play = play
        self._retry = retry
        self._server = Server(client, cipher, retry=retry)
        self._data = {g.key: State(g) for g in (games or GAMES.values())}
        self._locks = {key: asyncio.Lock() for key in self._data}
        # Games on MagicOnion have their own platform client and table key.
        self._bundles = {
            key: MagicOnionClient(data.game.grpc, cipher, secure=data.game.grpc.secure)
            for key, data in self._data.items()
            if data.game.grpc is not None
        }
        self._ciphers = {key: client.cipher for key, client in self._bundles.items()}
        self.ready = asyncio.Event()

    @property
    def server(self) -> Server:
        return self._server

    def get(self, key: str) -> State:
        try:
            return self._data[key]
        except KeyError:
            raise KeyError(f"Unknown game {key!r}.") from None

    def __iter__(self) -> Iterator[State]:
        return iter(self._data.values())

    async def close(self) -> None:
        for client in self._bundles.values():
            await client.close()

    async def wait_until_ready(self) -> None:
        await self.ready.wait()

    async def sync_basic_game(self, game: Game) -> bool:
        async with self._locks[game.key]:
            data = self._data[game.key]
            try:
                info = await fetch_store_info(
                    game, self._client, self._play, retry=self._retry
                )
                data.store = info
                data.icon_url = info.icon_url or data.icon_url

                data.manifest = await fetch_manifest(
                    self._client,
                    game,
                    info.version,
                    known=data.manifest,
                    retry=self._retry,
                )
                if game.has_catalog:
                    resource_version = data.manifest.resource_version
                    if resource_version is None:
                        raise ManifestError(
                            f"{game.key}: the manifest has no ResourceVersion."
                        )
                    addressables = await self._addressables(data)
                    data.catalog = await sync_catalog(
                        self._client,
                        game,
                        self.store,
                        resource_version,
                        known=data.catalog,
                        retry=self._retry,
                        addressables=addressables,
                    )
            except (ServiceError, httpx.HTTPError, OSError, CatalogError) as exc:
                logger.warning("%s: Basic sync failed: %s", game.key, exc)
                return False
            except Exception:
                logger.exception("%s: Basic sync failed unexpectedly.", game.key)
                return False
            return True

    async def _addressables(self, data: State) -> str | None:
        """The Addressables version in the game's APK settings, or None if the APK
        or its settings cannot be read."""
        if self._apks is None:
            return None
        game = data.game
        found = await self._apks.newest_file(game.key, SETTINGS_MEMBER)
        if found is None:
            return None
        apk, settings = found
        try:
            version = addressables_version(settings)
        except CatalogError as exc:
            logger.warning("%s: %s: %s", game.key, apk, exc)
            return None
        if version != data.addressables:
            logger.info("%s: Addressables %s (from %s).", game.key, version, apk)
            data.addressables = version
        return version

    async def sync_tables_game(self, game: Game) -> bool:
        if game.is_catalog_only and game.grpc is None:
            return True
        async with self._locks[game.key]:
            data = self._data[game.key]
            if data.manifest is None:
                logger.info("%s: No manifest yet; skipping the table sync.", game.key)
                return False
            try:
                result = await sync_tables(
                    game,
                    data.manifest,
                    server=self._server,
                    client=self._client,
                    cipher=self._ciphers.get(game.key, self._cipher),
                    store=self.store,
                    loaded=data.loaded_tables,
                    retry=self._retry,
                    bundles=self._bundles.get(game.key),
                )
            except (ServiceError, httpx.HTTPError, OSError) as exc:
                logger.warning("%s: Table sync failed: %s", game.key, exc)
                return False
            except Exception:
                logger.exception("%s: Table sync failed unexpectedly.", game.key)
                return False
            data.loaded_tables = result.loaded
            if result.downloaded:
                logger.info("%s: Updated %s.", game.key, ", ".join(result.downloaded))
            return not result.failed

    async def is_online(self, game: Game) -> bool:
        """Whether the game is out of maintenance, asked of the live servers.

        Catalog-only games have no game server to ask; for them an empty
        ``MaintenanceUrl`` in the manifest is all there is. Any failure to find
        out counts as offline.
        """
        try:
            manifest = await fetch_manifest(
                self._client,
                game,
                known=self._data[game.key].manifest,
                retry=self._retry,
            )
            if manifest.maintenance_url:
                return False
            if game.is_catalog_only:
                return True
            answer = await self._server.check_asset_bundle(manifest)
        except (ServiceError, httpx.HTTPError, ValueError) as exc:
            logger.info("%s: Could not tell if the game is online: %s", game.key, exc)
            return False
        return answer.get("code") == 1000

    async def sync_basic(self) -> list[str]:
        return [
            key
            for key, data in self._data.items()
            if not await self.sync_basic_game(data.game)
        ]

    async def sync_tables(self) -> list[str]:
        return [
            key
            for key, data in self._data.items()
            if not await self.sync_tables_game(data.game)
        ]

    async def sync_all(self) -> None:
        try:
            for key in await self.sync_basic():
                logger.warning("%s: No basic data yet.", key)
            for key in await self.sync_tables():
                logger.warning("%s: Tables are not up to date.", key)
        except asyncio.CancelledError:
            raise
        except BaseException:
            self.ready.set()
            raise
        self.ready.set()
