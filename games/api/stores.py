"""The app stores' listings of a game: the newest version, and its icon."""

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx
from gplaydl.api import (
    AuthExpiredError,
    PlayAPIError,
    get_delivery,
    get_details,
    purchase,
)
from gplaydl.auth import DispenserError, ensure_auth
from packaging.version import InvalidVersion, Version

from games.api.http import DEFAULT_RETRY, RetryPolicy, send
from games.errors import PlayStoreError
from games.models import AppStoreLookup, Game

logger = logging.getLogger(__name__)

ITUNES_LOOKUP_URL = "https://itunes.apple.com/lookup"


@dataclass(frozen=True, slots=True)
class AppStoreListing:
    """A game's App Store version and icon."""

    version: str
    icon_url: str


async def lookup_app_store(
    client: httpx.AsyncClient,
    lookup: AppStoreLookup,
    *,
    retry: RetryPolicy = DEFAULT_RETRY,
) -> AppStoreListing | None:
    """The game's App Store listing, or None if the store does not know it."""
    response = await send(
        client, "GET", ITUNES_LOOKUP_URL, params=lookup.params, retry=retry
    )
    response.raise_for_status()
    # iTunes serves JSON as text/javascript and may leave raw newlines inside
    # strings (release notes), which only a non-strict parse accepts.
    results = json.loads(response.text, strict=False).get("results") or []
    if not results:
        return None
    return AppStoreListing(
        version=results[0]["version"], icon_url=results[0]["artworkUrl100"]
    )


@dataclass(frozen=True, slots=True)
class PlayDetails:
    """A game's Google Play version name and code."""

    version_string: str
    version_code: int


class PlayStore:
    """Google Play through ``gplaydl``; its calls block, so they run in threads."""

    def __init__(self) -> None:
        self._auth_lock = asyncio.Lock()

    async def _auth(self, *, refresh: bool = False) -> dict[str, Any]:
        async with self._auth_lock:
            auth: dict[str, Any] | None = await asyncio.to_thread(
                ensure_auth, force_refresh=refresh
            )
        if not auth:
            raise PlayStoreError("Could not get a Google Play token.")
        return auth

    async def _run[T](self, call: Callable[[dict[str, Any]], T]) -> T:
        try:
            auth = await self._auth()
            try:
                return await asyncio.to_thread(call, auth)
            except AuthExpiredError:
                auth = await self._auth(refresh=True)
                return await asyncio.to_thread(call, auth)
        except PlayStoreError:
            raise
        except (PlayAPIError, DispenserError, httpx.HTTPError, OSError) as exc:
            raise PlayStoreError(f"Google Play lookup failed: {exc}") from exc

    async def details(self, package: str) -> PlayDetails:
        details = await self._run(lambda auth: get_details(package, auth))
        return PlayDetails(details.version_string, details.version_code)

    async def split_url(
        self, package: str, version_code: int, split_name: str
    ) -> str | None:
        """Download URL of the named split APK (e.g. ``base_assets``), if any."""
        token = await self._run(lambda auth: purchase(package, version_code, auth))
        delivery = await self._run(
            lambda auth: get_delivery(package, version_code, auth, token)
        )
        for split in delivery.splits:
            if split.name == split_name:
                return str(split.url)
        return None


@dataclass(frozen=True, slots=True)
class StoreInfo:
    """What the stores say about a game."""

    version: str  # the newest of the store versions and the game's floor
    icon_url: str | None


def _parsed(text: str | None) -> Version | None:
    try:
        return Version(text) if text else None
    except InvalidVersion:
        logger.warning("Ignoring unparsable store version %r.", text)
        return None


async def fetch_store_info(
    game: Game,
    client: httpx.AsyncClient,
    play: PlayStore | None,
    *,
    retry: RetryPolicy = DEFAULT_RETRY,
) -> StoreInfo:
    """The newest version of a game from Google Play, the App Store and its floor.

    A store that cannot be reached is skipped; unlisted games only have the floor.
    """
    if game.is_unlisted:
        return StoreInfo(game.version_floor, game.icon_url)

    android = ios = icon = None
    if play is not None:
        try:
            android = (await play.details(game.package_name)).version_string
        except PlayStoreError:
            logger.warning("%s: Google Play lookup failed.", game.key, exc_info=True)

    if game.app_store is not None:
        try:
            listing = await lookup_app_store(client, game.app_store, retry=retry)
        except httpx.HTTPError, ValueError, KeyError, AttributeError:
            logger.warning("%s: App Store lookup failed.", game.key, exc_info=True)
        else:
            if listing is not None:
                ios, icon = listing.version, listing.icon_url

    candidates = [
        text
        for text in (android, ios, game.version_floor)
        if text and _parsed(text) is not None
    ]
    version = max(candidates, key=Version)
    return StoreInfo(version, icon)
