import asyncio
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field

import httpx

from .assets import AssetContext, AssetContextError, tables_to_download
from .crypto import Cipher, CryptoError
from .errors import DataSyncError, ServerError
from .http import DEFAULT_RETRY, RetryPolicy, fetch
from .magic_onion import MagicOnionClient, fetch_bundle_context
from .manifest import Manifest
from .models import Game
from .server import Server
from .storage import REFERENCE_FIELDS, DataStore, Table, prune_referenced, slim

logger = logging.getLogger(__name__)


async def _prune_tables(
    store: DataStore,
    game: Game,
    tables: dict[str, Table],
    downloaded: list[str],
    loaded: LoadedTables | None,
) -> None:
    """Keep of the big lookup tables what the others refer to (``prune_referenced``)."""
    # What was kept from an earlier round is already pruned. If anything it is
    # pruned by changed, the whole table is needed again.
    if loaded is not None and not downloaded:
        return
    for name in REFERENCE_FIELDS:
        if name not in tables:
            continue
        if name not in downloaded:
            full = await store.read_table(game.key, name)
            if full is None:
                continue
            tables[name] = full
        pruned = await asyncio.to_thread(prune_referenced, name, tables)
        if pruned is not None:
            tables[name] = pruned


@dataclass(frozen=True, slots=True)
class LoadedTables:
    assets: AssetContext
    tables: Mapping[str, Table] = field(repr=False)


@dataclass(frozen=True, slots=True)
class TableSyncResult:
    loaded: LoadedTables
    downloaded: tuple[str, ...]
    failed: Mapping[str, str]
    online: bool


async def _bundle_context(
    game: Game,
    bundles: MagicOnionClient,
    client: httpx.AsyncClient,
    retry: RetryPolicy,
) -> AssetContext | None:
    """The asset context of a MagicOnion game, or None if it cannot be had."""
    assert game.grpc is not None
    try:
        check = await bundles.check_asset_bundle()
        context = await fetch_bundle_context(client, game.grpc, check, retry=retry)
        return context.to_asset_context()
    except (ServerError, AssetContextError) as exc:
        logger.info("%s: no asset context from the server (%s).", game.key, exc)
        return None


async def _current_index(
    game: Game,
    manifest: Manifest,
    server: Server,
    stored: AssetContext | None,
    bundles: MagicOnionClient | None = None,
    client: httpx.AsyncClient | None = None,
    retry: RetryPolicy = DEFAULT_RETRY,
) -> tuple[AssetContext, bool]:
    if game.is_unlisted:
        if stored is None:
            raise DataSyncError(f"{game.key}: an unlisted game needs a stored a.json.")
        return stored, False

    if game.grpc is not None and bundles is not None and client is not None:
        fresh = await _bundle_context(game, bundles, client, retry)
        if fresh is not None:
            return fresh, True
    else:
        answer = None
        try:
            answer = await server.check_asset_bundle(manifest)
        except ServerError as exc:
            logger.info("%s: no asset context from the server (%s).", game.key, exc)
        if answer is not None and answer.get("code") == 1000:
            try:
                return AssetContext.from_json(answer.get("result")), True
            except AssetContextError:
                logger.warning("%s: the server's asset context is malformed.", game.key)

    if stored is None:
        raise DataSyncError(
            f"{game.key}: the server gave no asset context and none is stored.",
            retryable=True,
        )
    return stored, False


async def _download_table(
    client: httpx.AsyncClient, cipher: Cipher, url: str, retry: RetryPolicy
) -> Table:
    response = await fetch(client, url, retry=retry)
    return await asyncio.to_thread(cipher.decode_table, response.content)


async def sync_tables(
    game: Game,
    manifest: Manifest,
    *,
    server: Server,
    client: httpx.AsyncClient,
    cipher: Cipher,
    store: DataStore,
    loaded: LoadedTables | None = None,
    retry: RetryPolicy = DEFAULT_RETRY,
    bundles: MagicOnionClient | None = None,
) -> TableSyncResult:
    stored = loaded.assets if loaded is not None else await store.read_assets(game.key)
    current, online = await _current_index(
        game, manifest, server, stored, bundles, client, retry
    )
    on_disk = await store.present_tables(game.key)
    wanted = set(tables_to_download(stored, current, on_disk))

    tables: dict[str, Table] = {}
    downloaded: list[str] = []
    failed: dict[str, str] = {}

    for name, file in current.table_files().items():
        if name not in wanted:
            kept = loaded.tables.get(name) if loaded is not None else None
            if kept is None:
                kept = await store.read_table(game.key, name)
            if kept is not None:
                tables[name] = kept
                continue
        try:
            table = await _download_table(client, cipher, file.url, retry)
        except (ServerError, CryptoError, httpx.HTTPError) as exc:
            logger.warning("%s: could not update %s: %s", game.key, name, exc)
            failed[name] = str(exc)
            previous = loaded.tables.get(name) if loaded is not None else None
            if previous is None:
                previous = await store.read_table(game.key, name)
            if previous is not None:
                tables[name] = previous
            continue
        await store.write_table(game.key, name, table)
        tables[name] = await asyncio.to_thread(slim, name, table)
        downloaded.append(name)

    await _prune_tables(store, game, tables, downloaded, loaded)

    effective = current
    if failed:
        old = stored.context if stored is not None else {}
        effective = current.with_tables({name: old.get(name) for name in failed})
    if stored is None or effective != stored:
        await store.write_assets(game.key, effective)

    return TableSyncResult(
        LoadedTables(effective, tables), tuple(downloaded), failed, online
    )
