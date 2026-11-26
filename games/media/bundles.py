"""Unity asset bundles: downloaded once, kept, and read in place.

Bundles are never unpacked to disk and never deleted. A file inside a bundle
is read straight from the bundle when it is needed. The layout is v0's
(``files/<game>/<bundle name>``), so bundles v0 already downloaded are reused.
"""

import asyncio
import logging
import os
from collections.abc import Callable, Collection, Iterator
from contextlib import contextmanager, suppress
from hashlib import sha1
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

import httpx
import UnityPy

from games.api.http import DEFAULT_RETRY, RetryPolicy, download
from ops.tuning import release_memory

if TYPE_CHECKING:
    from games.media.apks import ApkStore

logger = logging.getLogger(__name__)


class BundleError(Exception):
    """A bundle could not be fetched or read."""


class BuiltInBundle(BundleError):
    """The bundle ships inside the game's APK and has no download URL."""

    def __init__(self, url: str) -> None:
        super().__init__(f"Built-in bundle: {url}")
        self.url = url


def bundle_name(url: str) -> str:
    """The file name of a bundle, from its URL (without any ``?query``)."""
    path = urlsplit(url).path if "://" in url else url
    return path.rstrip("/").rsplit("/", 1)[-1]


def asset_name(key: str) -> str:
    """The name Unity gives an asset inside a bundle: the key's file name
    without its extension (``sounds/a/b/song_7.bytes`` is ``song_7``)."""
    return PurePosixPath(key).stem


type Source = Path | bytes  # a bundle on disk, or one read out of an APK


def load_environment(source: Source) -> Any:
    """Open a bundle with UnityPy. Raises :class:`BundleError` if it is absent."""
    if isinstance(source, Path):
        if not source.is_file():
            raise BundleError(f"{source.name} is not on disk.")
        return UnityPy.load(str(source))
    return UnityPy.load(source)


@contextmanager
def open_environment(source: Source) -> Iterator[Any]:
    """:func:`load_environment`, released as soon as the ``with`` block ends."""
    environment = load_environment(source)
    try:
        yield environment
    finally:
        with suppress(Exception):
            environment.files.clear()
            environment.cabs.clear()
        del environment
        release_memory()


def describe(source: Source) -> str:
    return source.name if isinstance(source, Path) else "a built-in bundle"


def read_text_assets(
    source: Source, names: Collection[str], ids: Collection[str] = ()
) -> dict[str, bytes]:
    """The raw bytes of text assets in a bundle, by name and by container id.

    A bundle may hold several assets of one name (the same chart as binary and
    as base64, say), so a name finds only the first of them. The id is what the
    catalog calls the asset, and the bundle's own container maps it to exactly
    one asset. The result is keyed by whatever was asked for; anything that is
    not in the bundle is left out.
    """
    wanted, wanted_ids = set(names), set(ids)
    try:
        with open_environment(source) as environment:
            return _read_wanted(environment, wanted, wanted_ids)
    except Exception as exc:  # UnityPy raises many kinds of errors
        raise BundleError(f"Could not read {describe(source)}: {exc!r}") from exc


def _read_wanted(
    environment: Any, wanted: set[str], wanted_ids: set[str]
) -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    objects = list(environment.objects)
    container: dict[str, int] = {}
    if wanted_ids:
        for obj in objects:
            if obj.type.name == "AssetBundle":
                for key, info in obj.read().m_Container:
                    if key in wanted_ids:
                        container[key] = info.asset.m_PathID
    by_path: dict[int, list[str]] = {}
    for key, path_id in container.items():
        by_path.setdefault(path_id, []).append(key)
    for obj in objects:
        if obj.type.name != "TextAsset":
            continue
        # Only the assets that were asked for are read: a bundle can hold
        # megabytes of others, and this runs several bundles at a time.
        name = obj.peek_name()
        wanted_name = name in wanted and name not in found
        if not wanted_name and obj.path_id not in by_path:
            continue
        script = obj.read().m_Script
        data = (
            script.encode("utf-8", "surrogateescape")
            if isinstance(script, str)
            else bytes(script)
        )
        if wanted_name:
            found[name] = data
        for key in by_path.get(obj.path_id, ()):
            found[key] = data
    return found


def _listing(folder: Path) -> set[str]:
    try:
        with os.scandir(folder) as entries:
            return {entry.name for entry in entries if entry.is_file()}
    except FileNotFoundError:
        return set()


class BundleStore:
    """Downloads and keeps the bundles of every game.

    Downloads are made once and under a lock per file. A built-in bundle (one the
    APK holds) is read from the APK instead.
    """

    def __init__(
        self,
        root: Path,
        client: httpx.AsyncClient,
        *,
        retry: RetryPolicy = DEFAULT_RETRY,
        apks: ApkStore | None = None,
    ) -> None:
        self._root = root
        self._client = client
        self._retry = retry
        self._apks = apks
        self._locks: dict[Path, asyncio.Lock] = {}

    def path(self, game_key: str, name: str) -> Path:
        """Where a bundle is kept on disk."""
        return self._root / "files" / game_key / name

    def plain_path(self, game_key: str, url: str) -> Path:
        """Where a plain (not bundled) file is kept.

        Such URLs carry a version in the query (``?v=21032201``) and the file
        name alone can repeat, so the whole URL is part of the local name.
        """
        digest = sha1(url.encode()).hexdigest()[:12]
        return (
            self._root / "files" / game_key / "plain" / f"{digest}_{bundle_name(url)}"
        )

    def on_disk(self, game_key: str) -> Callable[[str, bool], bool]:
        """A check of which files of a game are on disk, from one look at its
        folders. Asking the file system about each of thousands of files costs
        seconds of CPU; this costs one listing for each folder. Blocking: call
        it in a thread."""
        folder = self._root / "files" / game_key
        names = _listing(folder)
        plain_names = _listing(folder / "plain")

        def has(url: str, plain: bool) -> bool:
            if not plain:
                return bundle_name(url) in names
            digest = sha1(url.encode()).hexdigest()[:12]
            return f"{digest}_{bundle_name(url)}" in plain_names

        return has

    async def fetch(self, game_key: str, url: str, *, plain: bool = False) -> Path:
        """The file's path, downloading it first if it is not on disk."""
        if not url.startswith(("http://", "https://")):
            raise BuiltInBundle(url)
        path = (
            self.plain_path(game_key, url)
            if plain
            else self.path(game_key, bundle_name(url))
        )
        lock = self._locks.setdefault(path, asyncio.Lock())
        async with lock:
            if await asyncio.to_thread(path.exists):
                return path
            try:
                await download(self._client, url, path, retry=self._retry)
            except httpx.HTTPError as exc:
                raise BundleError(f"Could not download {url}: {exc!r}") from exc
        return path

    async def open(self, game_key: str, url: str) -> Source:
        """A bundle, ready to read: its path, or its bytes when it is built in.

        Raises :class:`BuiltInBundle` if it is built in and cannot be found.
        """
        if url.startswith(("http://", "https://")):
            return await self.fetch(game_key, url)
        data = await self._apks.read(game_key, url) if self._apks else None
        if data is None:
            raise BuiltInBundle(url)
        return data

    async def read(
        self, game_key: str, url: str, names: Collection[str], ids: Collection[str] = ()
    ) -> dict[str, bytes]:
        """Get the bundle if needed, then read text assets by name and by id."""
        source = await self.open(game_key, url)
        return await asyncio.to_thread(read_text_assets, source, names, ids)
