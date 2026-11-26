"""Keeping a game's Unity Addressables catalog downloaded and parsed."""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from games.api.http import DEFAULT_RETRY, RetryPolicy, download, is_retryable_status
from games.data.catalog import BinaryCatalog, CatalogError, load_catalog
from games.data.storage import DataStore
from games.errors import DataSyncError
from games.models import Game

logger = logging.getLogger(__name__)

CATALOG_FALLBACK_STEPS = 5
MISSING_STATUSES = frozenset({403, 404})
STATE_FILE = "state.json"


@dataclass(frozen=True, slots=True)
class LoadedCatalog:
    """A parsed catalog, the version asked for and the one it was found under."""

    requested: str
    effective: str
    catalog: BinaryCatalog = field(repr=False)


def addressables_version(settings: bytes) -> str:
    """``m_AddressablesVersion`` from the game's Addressables settings.

    The catalog's URL has this version in its path
    (``.../Android/<addressables version>/catalog_<n>.bin``).
    """
    try:
        version = json.loads(settings)["m_AddressablesVersion"]
    except (ValueError, KeyError, TypeError) as exc:
        raise CatalogError("The Addressables settings cannot be read.") from exc
    if not isinstance(version, str) or not version:
        raise CatalogError("The Addressables settings have no version.")
    return version


def _previous(resource_version: str) -> str | None:
    if resource_version.isdecimal() and int(resource_version) > 0:
        return str(int(resource_version) - 1)
    return None


def _read_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def _remove_others(directory: Path, keep: set[str]) -> None:
    for path in directory.iterdir():
        if path.is_file() and path.name not in keep:
            path.unlink(missing_ok=True)


async def _load(path: Path) -> BinaryCatalog | None:
    data = await asyncio.to_thread(_read_bytes, path)
    if data is None:
        return None
    try:
        return await load_catalog(data)
    except CatalogError:
        logger.warning("%s is not a valid catalog; it will be downloaded again.", path)
        return None


async def _download(
    client: httpx.AsyncClient,
    game: Game,
    directory: Path,
    resource_version: str,
    retry: RetryPolicy,
    url: str,
) -> str:
    version = resource_version
    for _ in range(CATALOG_FALLBACK_STEPS + 1):
        try:
            await download(
                client,
                url.format(version=version),
                directory / f"{version}.bin",
                retry=retry,
            )
            return version
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status not in MISSING_STATUSES:
                raise DataSyncError(
                    f"{game.key}: the catalog server answered {status}.",
                    retryable=is_retryable_status(status),
                ) from exc
        except httpx.TransportError as exc:
            raise DataSyncError(
                f"{game.key}: could not download the catalog: {exc!r}", retryable=True
            ) from exc
        previous = _previous(version)
        if previous is None:
            break
        version = previous
    raise DataSyncError(
        f"{game.key}: there is no catalog for resource version {resource_version} "
        f"or the {CATALOG_FALLBACK_STEPS} before it."
    )


async def sync_catalog(
    client: httpx.AsyncClient,
    game: Game,
    store: DataStore,
    resource_version: str,
    *,
    known: LoadedCatalog | None = None,
    retry: RetryPolicy = DEFAULT_RETRY,
    addressables: str | None = None,
) -> LoadedCatalog:
    """The game's catalog for a resource version, downloading it if it is new.

    ``addressables`` is the Addressables version of the game's build, which is
    part of the URL. It is only needed to download; a catalog already kept for
    the resource version is used without it.
    """
    if known is not None and known.requested == resource_version:
        return known

    directory = store.catalog_dir(game.key)
    state = await store.read_json(directory / STATE_FILE)
    if isinstance(state, dict) and state.get("requested") == resource_version:
        effective = state.get("effective")
        if (
            isinstance(effective, str)
            and (catalog := await _load(directory / f"{effective}.bin")) is not None
        ):
            return LoadedCatalog(resource_version, effective, catalog)

    if game.catalog_url is None:
        raise DataSyncError(f"{game.key}: there is no catalog URL.")
    if addressables is None:
        raise DataSyncError(
            f"{game.key}: the Addressables version is not known, as the game's "
            "APK could not be read."
        )
    url = game.catalog_url.replace("{addressables}", addressables)
    effective = await _download(client, game, directory, resource_version, retry, url)
    catalog = await _load(directory / f"{effective}.bin")
    if catalog is None:
        await asyncio.to_thread(
            (directory / f"{effective}.bin").unlink, missing_ok=True
        )
        raise DataSyncError(f"{game.key}: the downloaded catalog cannot be read.")

    await store.write_json(
        directory / STATE_FILE, {"requested": resource_version, "effective": effective}
    )
    await asyncio.to_thread(_remove_others, directory, {f"{effective}.bin", STATE_FILE})
    return LoadedCatalog(resource_version, effective, catalog)
