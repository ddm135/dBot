"""Album art and deck emblems.

A table refers to an image in one of three ways: a full URL, a code in the
``URLs`` table, or a catalog key. URLs are handed to Discord as they are.
A catalog key names an image inside a bundle; it is decoded from the kept
bundle on demand (never saved as a file) and sent as an attachment.
"""

import asyncio
import logging
import time
from collections import OrderedDict
from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass
from io import BytesIO
from typing import TYPE_CHECKING, Any

from games.media.bundles import (
    BuiltInBundle,
    BundleError,
    BundleStore,
    Source,
    asset_name,
    bundle_name,
    describe,
    open_environment,
)
from ops.tuning import release_memory

if TYPE_CHECKING:
    from games.index import Index
    from games.service import DataService

logger = logging.getLogger(__name__)

IMAGE_TYPES = ("Texture2D", "Sprite")
CACHE_SIZE = 256
MISS_SECONDS = 600.0


@dataclass(frozen=True, slots=True)
class PrefetchResult:
    """How a prefetch went: bundles kept, downloaded, failed, or built in."""

    kept: int = 0  # bundles already on disk
    downloaded: int = 0
    failed: int = 0
    built_in: int = 0  # in the game's APK, not downloadable


PREFETCH_CONCURRENCY = 3


@dataclass(frozen=True, slots=True)
class Picture:
    """An image: either a URL for Discord to load, or PNG bytes to attach."""

    url: str | None = None
    data: bytes | None = None
    filename: str = "image.png"


def read_images(
    source: Source, names: set[str], ids: Collection[str] = ()
) -> dict[str, bytes]:
    """PNG bytes of textures (or sprites) in a bundle, by name and by container id.

    A texture wins over a sprite of the same name. A bundle can hold several
    images of one name (a border updated under a new dated path, say), which a
    name cannot tell apart; the id the catalog gives names exactly one. The
    result is keyed by whatever was asked for. Anything not in the bundle, or
    that cannot be decoded, is left out.
    """
    wanted_ids = set(ids)
    candidates: dict[str, Any] = {}
    by_id: dict[str, Any] = {}
    found: dict[str, bytes] = {}
    try:
        with open_environment(source) as environment:
            objects = list(environment.objects)
            id_paths: dict[int, list[str]] = {}
            if wanted_ids:
                for obj in objects:
                    if obj.type.name == "AssetBundle":
                        for key, info in obj.read().m_Container:
                            if key in wanted_ids:
                                id_paths.setdefault(info.asset.m_PathID, []).append(key)
            for obj in objects:
                if obj.type.name not in IMAGE_TYPES:
                    continue
                by_name = obj.peek_name() in names
                if not by_name and obj.path_id not in id_paths:
                    continue
                asset = obj.read()
                for key in id_paths.get(obj.path_id, ()):
                    by_id[key] = asset
                if not by_name:
                    continue
                # A texture is the real image; a sprite of the same name is a view of it.
                if obj.type.name == "Texture2D" or asset.m_Name not in candidates:
                    candidates[asset.m_Name] = asset
            # Decoded inside the block: an image reads from the bundle's data.
            for name, asset in [*candidates.items(), *by_id.items()]:
                try:
                    buffer = BytesIO()
                    asset.image.save(buffer, "PNG")
                except Exception:  # noqa: BLE001 - a bad texture should not hide the others
                    logger.warning(
                        "Could not decode image %s in %s.", name, describe(source)
                    )
                    continue
                found[name] = buffer.getvalue()
    except Exception as exc:  # UnityPy raises many kinds of errors
        raise BundleError(f"Could not read {describe(source)}: {exc!r}") from exc
    finally:
        candidates.clear()
        by_id.clear()
        release_memory()
    return found


class ImageService:
    """Album art and group emblems, from the game's bundles.

    Pictures are decoded only when asked for; what is prefetched is the bundles.
    """

    def __init__(
        self,
        bundles: BundleStore,
        games: DataService,
        indexes: Any,
        *,
        cache_size: int = CACHE_SIZE,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._bundles = bundles
        self._games = games
        self._indexes = indexes
        self._cache: OrderedDict[tuple[str, str], Picture] = OrderedDict()
        self._misses: dict[tuple[str, str], float] = {}  # when to try again
        self._warned: set[tuple[str, str]] = set()
        self._size = cache_size
        self._clock = clock

    async def album(self, game_key: str, song_code: int) -> Picture | None:
        """The art of a song's album, or None if the game has none."""
        index: Index | None = self._indexes.get(game_key)
        if index is None:
            return None
        return await self._picture(game_key, index, index.album_ref(song_code))

    def album_bundle_urls(self, game_key: str) -> list[str]:
        """The bundles that hold the game's album art, each once."""
        return self._bundle_urls(
            game_key,
            lambda index: (index.album_ref(code) for code in index.decks.songs),
        )

    def emblem_bundle_urls(self, game_key: str) -> list[str]:
        """The bundles that hold the groups' emblems (their icons), each once."""
        return self._bundle_urls(
            game_key,
            lambda index: (
                deck.raw.get("emblemImage") for deck in index.decks.decks.values()
            ),
        )

    def _bundle_urls(
        self, game_key: str, refs: Callable[[Index], Iterable[object]]
    ) -> list[str]:
        """The bundles holding the pictures ``refs`` names, each once.

        Only a picture named by a catalog key is in a bundle; a URL is Discord's
        to load.
        """
        index: Index | None = self._indexes.get(game_key)
        catalog = self._games.get(game_key).catalog
        if index is None or catalog is None:
            return []
        urls: dict[str, None] = {}
        for ref in refs(index):
            if not isinstance(ref, str) or not ref or index.resolve_url(ref):
                continue
            try:
                found = catalog.catalog.bundle_urls(ref)
            except KeyError:
                continue
            urls.update(dict.fromkeys(u for u in found[:1] if u))
        return list(urls)

    async def prefetch_albums(self, game_key: str) -> PrefetchResult:
        """Download every album bundle not yet kept (nothing is decoded or saved
        as an image; pictures still come from the bundles when asked for)."""
        return await self._prefetch(game_key, self.album_bundle_urls(game_key))

    async def prefetch_emblems(self, game_key: str) -> PrefetchResult:
        """:meth:`prefetch_albums` for the groups' emblems."""
        return await self._prefetch(game_key, self.emblem_bundle_urls(game_key))

    async def _prefetch(self, game_key: str, urls: list[str]) -> PrefetchResult:
        gate = asyncio.Semaphore(PREFETCH_CONCURRENCY)
        counts = dict.fromkeys(("kept", "downloaded", "failed", "built_in"), 0)

        async def one(url: str) -> None:
            async with gate:
                if not url.startswith(("http://", "https://")):
                    counts["built_in"] += 1
                    return
                path = self._bundles.path(game_key, bundle_name(url))
                had = await asyncio.to_thread(path.exists)
                try:
                    await self._bundles.fetch(game_key, url)
                except BundleError as exc:
                    counts["failed"] += 1
                    logger.warning("%s: album bundle: %s", game_key, exc)
                    return
                counts["downloaded" if not had else "kept"] += 1

        await asyncio.gather(*(one(url) for url in urls))
        return PrefetchResult(**counts)

    async def emblem(self, game_key: str, deck_code: int) -> Picture | None:
        """The emblem of a deck, or None if it has none."""
        index: Index | None = self._indexes.get(game_key)
        deck = index.decks.decks.get(deck_code) if index else None
        if index is None or deck is None:
            return None
        return await self._picture(game_key, index, deck.raw.get("emblemImage"))

    async def _picture(
        self, game_key: str, index: Index, ref: object
    ) -> Picture | None:
        if url := index.resolve_url(ref):
            return Picture(url=url)
        if not isinstance(ref, str) or not ref:
            return None
        cache_key = (game_key, ref)
        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            return self._cache[cache_key]
        if self._clock() < self._misses.get(cache_key, 0.0):
            return None  # failed a moment ago; do not hammer the CDN or Google Play
        picture = await self.from_catalog(game_key, ref)
        if picture is None:
            # A failure is remembered only briefly: the cause (an APK still
            # downloading, a CDN error) is usually gone soon.
            self._misses[cache_key] = self._clock() + MISS_SECONDS
            return None
        self._cache[cache_key] = picture
        self._misses.pop(cache_key, None)
        while len(self._cache) > self._size:
            self._cache.popitem(last=False)
        return picture

    async def from_catalog(self, game_key: str, key: str) -> Picture | None:
        """The image a catalog key names, decoded from its bundle (not cached)."""
        catalog = self._games.get(game_key).catalog
        if catalog is None:
            return None
        try:
            urls = [u for u in catalog.catalog.bundle_urls(key) if u]
        except KeyError:
            return None
        if not urls:
            return None
        name = asset_name(key)
        ids = [i for i in catalog.catalog.internal_ids(key) if i]
        try:
            source = await self._bundles.open(game_key, urls[0])
            found = await asyncio.to_thread(read_images, source, {name}, ids)
        except BuiltInBundle:
            self._warn_once(
                game_key, urls[0], "is built in and the game's APK is not available"
            )
            return None
        except BundleError as exc:
            logger.warning("%s: image %s: %s", game_key, key, exc)
            return None
        # The id names one image; the name is only the first of that name.
        data = next((found[i] for i in ids if i in found), None) or found.get(name)
        if not data:
            self._warn_once(game_key, key, f"has no image named {name!r} in its bundle")
            return None
        return Picture(data=data, filename=f"{name}.png")

    def _warn_once(self, game_key: str, subject: str, reason: str) -> None:
        if (game_key, subject) not in self._warned:
            self._warned.add((game_key, subject))
            logger.warning("%s: %s %s.", game_key, subject, reason)
