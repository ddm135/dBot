"""Keeping a game's data tables current: what the server says is new, downloaded,
decrypted, stored, and cut down to what the bot reads.
"""

import asyncio
import logging
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from games.api.crypto import Cipher, CryptoError
from games.api.http import DEFAULT_RETRY, RetryPolicy, fetch
from games.api.magic_onion import MagicOnionClient, fetch_bundle_context
from games.api.manifest import Manifest
from games.data.schema import AssetContext, AssetContextError, tables_to_download
from games.data.storage import (
    REFERENCE_FIELDS,
    DataStore,
    Table,
    prune_referenced,
    slim,
)
from games.errors import DataSyncError, ServerError
from games.models import Game

logger = logging.getLogger(__name__)


async def _prune_tables(
    store: DataStore,
    game: Game,
    tables: dict[str, Table],
    downloaded: list[str],
    loaded: LoadedTables | None,
    saved: Collection[str] = (),
) -> None:
    """Keep of the big lookup tables what the others refer to (``prune_referenced``)."""
    # What was kept from an earlier round is already pruned. If anything it is
    # pruned by changed, the whole table is needed again.
    if loaded is not None and not downloaded:
        return
    for name in REFERENCE_FIELDS:
        if name not in tables:
            continue
        if name in saved and not downloaded:
            continue  # read already pruned, from the copy kept on disk
        if name not in downloaded:
            full = await store.read_table(game.key, name)
            if full is None:
                continue
            tables[name] = full
        pruned = await asyncio.to_thread(prune_referenced, name, tables)
        if pruned is not None:
            tables[name] = pruned
            await store.write_kept(game.key, name, pruned)


@dataclass(frozen=True, slots=True)
class LoadedTables:
    """A game's asset listing and the tables read for it."""

    assets: AssetContext
    tables: Mapping[str, Table] = field(repr=False)


@dataclass(frozen=True, slots=True)
class TableSyncResult:
    """What a sync did: the tables now loaded, which were downloaded, and which failed
    (and why).
    """

    loaded: LoadedTables
    downloaded: tuple[str, ...]
    failed: Mapping[str, str]


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


class AssetServer(Protocol):
    """What the table sync asks of the game server (the real one is ``Server``)."""

    async def check_asset_bundle(self, manifest: Manifest) -> dict[str, Any]: ...


async def _current_index(
    game: Game,
    manifest: Manifest,
    server: AssetServer,
    stored: AssetContext | None,
    bundles: MagicOnionClient | None = None,
    client: httpx.AsyncClient | None = None,
    retry: RetryPolicy = DEFAULT_RETRY,
) -> AssetContext:
    if game.is_unlisted:
        if stored is None:
            raise DataSyncError(f"{game.key}: an unlisted game needs a stored a.json.")
        return stored

    if game.grpc is not None and bundles is not None and client is not None:
        fresh = await _bundle_context(game, bundles, client, retry)
        if fresh is not None:
            return fresh
    else:
        answer = None
        try:
            answer = await server.check_asset_bundle(manifest)
        except ServerError as exc:
            logger.info("%s: no asset context from the server (%s).", game.key, exc)
        if answer is not None and answer.get("code") == 1000:
            try:
                return AssetContext.from_json(answer.get("result"))
            except AssetContextError:
                logger.warning("%s: the server's asset context is malformed.", game.key)

    if stored is None:
        raise DataSyncError(
            f"{game.key}: the server gave no asset context and none is stored.",
            retryable=True,
        )
    return stored


async def _download_table(
    client: httpx.AsyncClient, cipher: Cipher, url: str, retry: RetryPolicy
) -> Table:
    response = await fetch(client, url, retry=retry)
    return await asyncio.to_thread(cipher.decode_table, response.content)


async def sync_tables(
    game: Game,
    manifest: Manifest,
    *,
    server: AssetServer,
    client: httpx.AsyncClient,
    cipher: Cipher,
    store: DataStore,
    loaded: LoadedTables | None = None,
    retry: RetryPolicy = DEFAULT_RETRY,
    bundles: MagicOnionClient | None = None,
) -> TableSyncResult:
    """Bring a game's tables up to date.

    Asks the server (or the MagicOnion server, or the stored listing for unlisted
    games) which files are new, downloads those, and reads the rest from disk, from
    the kept copies where they are still valid. A table that fails keeps its older
    copy and is listed in ``failed``.
    """
    # `stored` is the listing from the last successful sync (what the files on disk
    # are); `current` is what the server lists now. The difference is the work.
    stored = loaded.assets if loaded is not None else await store.read_assets(game.key)
    current = await _current_index(
        game, manifest, server, stored, bundles, client, retry
    )
    on_disk = await store.present_tables(game.key)
    wanted = set(tables_to_download(stored, current, on_disk))

    tables: dict[str, Table] = {}
    downloaded: list[str] = []
    saved: set[str] = set()
    failed: dict[str, str] = {}

    for name, file in current.table_files().items():
        # Sources for an unchanged table, cheapest first: the copy in memory, the cut-
        # down copy on disk, then the full file. Only if none exists is it downloaded.
        if name not in wanted:
            kept = loaded.tables.get(name) if loaded is not None else None
            if kept is None and name in REFERENCE_FIELDS:
                # Cut down and pruned by an earlier run: no need to read it all.
                kept = await store.read_kept(game.key, name)
                if kept is not None:
                    saved.add(name)
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
            # One bad table must not take the game down: keep serving its old copy.
            previous = loaded.tables.get(name) if loaded is not None else None
            if previous is None:
                previous = await store.read_table(game.key, name)
            if previous is not None:
                tables[name] = previous
            continue
        # The full file goes to disk; memory keeps only the slim version, because the
        # full tables are large and the bot reads few of their columns. slim is CPU
        # heavy, so it runs in a thread rather than blocking the event loop.
        await store.write_table(game.key, name, table)
        tables[name] = await asyncio.to_thread(slim, name, table)
        downloaded.append(name)

    await _prune_tables(store, game, tables, downloaded, loaded, saved)

    # Record the new listing, except that a failed table keeps its old entry: the
    # next sync then sees it as out of date and tries again, instead of treating the
    # stale copy as current.
    effective = current
    if failed:
        old = stored.context if stored is not None else {}
        effective = current.with_tables({name: old.get(name) for name in failed})
    # Skip the write when nothing changed, so an idle sync does not touch the disk.
    if stored is None or effective != stored:
        await store.write_assets(game.key, effective)

    return TableSyncResult(LoadedTables(effective, tables), tuple(downloaded), failed)
