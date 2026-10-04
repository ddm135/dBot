"""Bundles that ship inside the game's APK.

Some catalog entries have no download URL: their ``internalId`` starts with
``{UnityEngine.AddressableAssets.Addressables.RuntimePath}``. Those bundles
are in the game's ``base_assets`` split APK from Google Play, under
``assets/aa/Android/``. The APK is downloaded once and kept; a bundle is read
out of it in memory (an APK is a zip) and never written to disk.
"""

import asyncio
import logging
import time
import zipfile
from collections import OrderedDict
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol

import httpx

from .errors import PlayStoreError
from .fields import FILE_FIELDS
from .http import DEFAULT_RETRY, RetryPolicy, download
from .registry import GAMES
from .stores import PlayDetails

logger = logging.getLogger(__name__)

SPLIT_NAME = "base_assets"
MEMBER_ROOT = "assets/aa/Android/"
SETTINGS_MEMBER = "assets/aa/settings.json"  # the Addressables runtime settings
RETRY_AFTER = 3600.0  # seconds before asking Google Play again after a miss
REFRESH_AFTER = 3600.0  # seconds before checking Google Play for a newer APK
CACHE_BYTES = 64 * 1024 * 1024


class Play(Protocol):
    async def details(self, package: str) -> PlayDetails: ...

    async def split_url(
        self, package: str, version_code: int, split_name: str
    ) -> str | None: ...


def member_name(url: str) -> str | None:
    """The path of a built-in bundle inside the APK, from its catalog id."""
    _, sep, tail = url.partition("/Android/")
    return f"{MEMBER_ROOT}{tail}" if sep and tail else None


def read_member(apk: Path, member: str) -> bytes | None:
    """One file from an APK, or None if it is not there (or the APK is bad)."""
    try:
        with zipfile.ZipFile(apk) as archive:
            try:
                return archive.read(member)
            except KeyError:
                return None
    except zipfile.BadZipFile, OSError:
        logger.warning("Could not read %s.", apk, exc_info=True)
        return None


class HasBundleUrls(Protocol):
    def bundle_urls(self, key: object) -> list[str | None]: ...


def needs_apk(
    tables: Mapping[str, Mapping[str, Mapping[str, object]]], catalog: HasBundleUrls
) -> bool:
    """Whether any file the tables refer to is a built-in bundle."""
    for table, fields in FILE_FIELDS.items():
        for entry in tables.get(table, {}).values():
            for field in fields:
                ref = entry.get(field)
                if not isinstance(ref, str) or not ref or ref.startswith("http"):
                    continue
                try:
                    urls = catalog.bundle_urls(ref)
                except KeyError:
                    continue
                if urls and urls[0] and not urls[0].startswith(("http://", "https://")):
                    return True
    return False


class ApkStore:
    def __init__(
        self,
        root: Path,
        client: httpx.AsyncClient,
        play: Play | None,
        *,
        retry: RetryPolicy = DEFAULT_RETRY,
        clock: Callable[[], float] = time.monotonic,
        cache_bytes: int = CACHE_BYTES,
    ) -> None:
        self._root = root
        self._client = client
        self._play = play
        self._retry = retry
        self._clock = clock
        self._cache_bytes = cache_bytes
        self._cache: OrderedDict[tuple[str, str], bytes] = OrderedDict()
        self._locks: dict[str, asyncio.Lock] = {}
        self._not_before: dict[str, float] = {}
        self._checked: dict[str, float] = {}

    def folder(self, game_key: str) -> Path:
        return self._root / "apks" / game_key

    def _kept(self, game_key: str) -> list[Path]:
        """APKs already on disk, newest first."""
        folder = self.folder(game_key)
        found = sorted(
            folder.glob("*.apk"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        return [p for p in found if p.is_file()]

    async def prefetch(self, game_key: str) -> Path | None:
        """Make sure the game has an APK, downloading the current one if none is kept.

        Done in the background, so a command never waits for the download.
        Returns the newest kept APK, or None if there is none.
        """
        async with self._locks.setdefault(game_key, asyncio.Lock()):
            kept = await asyncio.to_thread(self._kept, game_key)
            if kept:
                return kept[0]
            if self._play is None or self._clock() < self._not_before.get(
                game_key, 0.0
            ):
                return None
            self._not_before[game_key] = self._clock() + RETRY_AFTER
            return await self._download_latest(game_key)

    async def newest_file(self, game_key: str, member: str) -> tuple[str, bytes] | None:
        """A file from the game's newest APK, with that APK's name.

        Unlike :meth:`read`, a kept older APK is not good enough: this is for
        files that change with the game version, so Google Play is asked (at
        most once an hour) whether there is a newer one to keep first.
        """
        async with self._locks.setdefault(game_key, asyncio.Lock()):
            if self._play is not None and self._clock() >= self._checked.get(
                game_key, 0.0
            ):
                self._checked[game_key] = self._clock() + REFRESH_AFTER
                await self._download_latest(game_key)
            kept = await asyncio.to_thread(self._kept, game_key)
            if not kept:
                return None
            data = await asyncio.to_thread(read_member, kept[0], member)
        return (kept[0].name, data) if data is not None else None

    async def read(self, game_key: str, url: str) -> bytes | None:
        """The built-in bundle's bytes, or None if it cannot be found."""
        member = member_name(url)
        if member is None:
            return None
        key = (game_key, member)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]

        async with self._locks.setdefault(game_key, asyncio.Lock()):
            if key in self._cache:  # another task found it meanwhile
                return self._cache[key]
            data = await self._find(game_key, member)
        if data is not None:
            self._remember(key, data)
        return data

    async def _find(self, game_key: str, member: str) -> bytes | None:
        for kept in await asyncio.to_thread(self._kept, game_key):
            data = await asyncio.to_thread(read_member, kept, member)
            if data is not None:
                return data
        if self._play is None or self._clock() < self._not_before.get(game_key, 0.0):
            return None

        # None of the kept APKs has it. A newer game version may.
        self._not_before[game_key] = self._clock() + RETRY_AFTER
        apk = await self._download_latest(game_key)
        if apk is None:
            return None
        data = await asyncio.to_thread(read_member, apk, member)
        if data is None:
            logger.warning("%s: %s is not in %s either.", game_key, member, apk.name)
        return data

    async def _download_latest(self, game_key: str) -> Path | None:
        game = GAMES.get(game_key)
        if game is None or self._play is None:
            return None
        try:
            details = await self._play.details(game.package_name)
            path = self.folder(game_key) / f"{details.version_string}.apk"
            if await asyncio.to_thread(path.exists):
                return None  # already searched above
            url = await self._play.split_url(
                game.package_name, details.version_code, SPLIT_NAME
            )
            if url is None:
                logger.warning("%s: Google Play has no %s split.", game_key, SPLIT_NAME)
                return None
            logger.info(
                "%s: Downloading the base assets of %s.",
                game_key,
                details.version_string,
            )
            await download(self._client, url, path, retry=self._retry)
        except (PlayStoreError, httpx.HTTPError) as exc:
            logger.warning("%s: Could not get the base assets APK: %s", game_key, exc)
            return None
        return path

    def _remember(self, key: tuple[str, str], data: bytes) -> None:
        if len(data) > self._cache_bytes:
            return
        self._cache[key] = data
        while sum(map(len, self._cache.values())) > self._cache_bytes:
            self._cache.popitem(last=False)
