import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self

import httpx
from packaging.version import InvalidVersion, Version

from games.errors import ManifestError
from games.http import DEFAULT_RETRY, RetryPolicy, is_retryable_status, send
from games.models import Game

logger = logging.getLogger(__name__)

MAX_HOPS = 8


@dataclass(frozen=True, slots=True)
class Manifest:
    raw: Mapping[str, Any]

    @classmethod
    def from_json(cls, data: object) -> Self:
        if not isinstance(data, Mapping):
            raise ManifestError("The manifest is not a JSON object.")
        active = data.get("ActiveVersion_Android")
        if not isinstance(active, str) or not active:
            raise ManifestError("The manifest has no ActiveVersion_Android.")
        return cls(data)

    def _text(self, key: str) -> str | None:
        value = self.raw.get(key)
        return str(value) if value not in (None, "") else None

    @property
    def active_version_android(self) -> str:
        return str(self.raw["ActiveVersion_Android"])

    @property
    def active_version_ios(self) -> str | None:
        return self._text("ActiveVersion_IOS")

    def latest_version(self, *others: str) -> str:
        candidates = [self.active_version_android, self.active_version_ios, *others]
        return max((v for v in candidates if v), key=_version)

    @property
    def resource_version(self) -> str | None:
        return self._text("ResourceVersion")

    @property
    def maintenance_url(self) -> str | None:
        return self._text("MaintenanceUrl")

    @property
    def music_rank_server_url(self) -> str | None:
        return self._text("MusicRankServerUrl")

    @property
    def server_url(self) -> str:
        url = self._text("ServerUrl")
        if url is None:
            raise ManifestError("The manifest has no ServerUrl.")
        return url


def _version(text: str) -> Version:
    try:
        return Version(text)
    except InvalidVersion as exc:
        raise ManifestError(f"Invalid version {text!r} in the manifest.") from exc


async def fetch_manifest(
    client: httpx.AsyncClient,
    game: Game,
    version: str | None = None,
    *,
    known: Manifest | None = None,
    retry: RetryPolicy = DEFAULT_RETRY,
) -> Manifest:
    floor = game.version_floor
    if version is None:
        candidates = [floor]
        if known is not None:
            candidates += [
                v for v in (known.active_version_android, known.active_version_ios) if v
            ]
        version = max(candidates, key=_version)

    for _ in range(MAX_HOPS):
        url = game.manifest_url_for(version)
        try:
            response = await send(client, "GET", url, retry=retry)
        except httpx.TransportError as exc:
            raise ManifestError(
                f"{game.key}: could not reach the manifest server: {exc!r}",
                retryable=True,
            ) from exc
        if is_retryable_status(response.status_code):
            raise ManifestError(
                f"{game.key}: the manifest server answered {response.status_code}.",
                retryable=True,
            )

        try:
            manifest = Manifest.from_json(json.loads(response.text))
        except json.JSONDecodeError:
            if _version(version) <= _version(floor):
                raise ManifestError(
                    f"{game.key}: there is no manifest for version {version} "
                    f"(HTTP {response.status_code})."
                ) from None
            logger.info(
                "%s: No manifest for %s, trying %s...", game.key, version, floor
            )
            version = floor
            continue

        if _version(manifest.active_version_android) <= _version(version):
            return manifest
        version = manifest.active_version_android

    raise ManifestError(f"{game.key}: The manifest version did not settle.")
