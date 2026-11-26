"""The platform server of games that use MagicOnion (gRPC with MessagePack bodies).

Every body is MessagePack, then AES-256-CBC with PKCS#7 padding, sent as
``IV || ciphertext``. The calls are unary: ``/IPlatform/<Method>``. The
``assetver`` and ``api-version`` headers are the ones the game's own client
filter adds; no session is needed for the platform calls.
"""

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self

import grpc
import grpc.aio
import httpx
import msgpack

from games.api.crypto import Cipher
from games.api.http import DEFAULT_RETRY, RetryPolicy, fetch
from games.data.schema import AssetContext
from games.errors import DataSyncError, ServerError
from games.models import GrpcConfig

logger = logging.getLogger(__name__)

SERVICE = "IPlatform"
TIMEOUT_SECONDS = 15.0

_RETRYABLE = {
    grpc.StatusCode.UNAVAILABLE,
    grpc.StatusCode.DEADLINE_EXCEEDED,
    grpc.StatusCode.INTERNAL,
    grpc.StatusCode.RESOURCE_EXHAUSTED,
}


def pack(value: Any, cipher: Cipher) -> bytes:
    """Encode ``value`` as MessagePack."""
    return cipher.seal(msgpack.packb(value, use_bin_type=True))


def unpack(data: bytes, cipher: Cipher) -> Any:
    """Decode a MessagePack body."""
    if not data:
        return None
    return msgpack.unpackb(cipher.unseal(data), raw=False, strict_map_key=False)


@dataclass(frozen=True, slots=True)
class BundleCheck:
    """The answer of ``CheckAssetBundle``."""

    asset_hash: str
    context: str  # the server path of the bundle directory
    skip: bool = False

    @classmethod
    def from_answer(cls, answer: object) -> Self:
        """The check from the server's decoded ``CheckAssetBundle`` answer."""
        if not isinstance(answer, Mapping):
            raise ServerError("CheckAssetBundle did not answer with a map.")
        asset_hash, context = answer.get("AssetHash"), answer.get("Context")
        if not isinstance(asset_hash, str) or not isinstance(context, str):
            raise ServerError("CheckAssetBundle has no AssetHash and Context.")
        # The server writes a trailing space after the path.
        path = context.strip().strip("/")
        if not path:
            raise ServerError("CheckAssetBundle gave an empty Context.")
        return cls(asset_hash, path, bool(answer.get("IsCheckSkip")))


class MagicOnionClient:
    """A gRPC channel to a MagicOnion server.

    Bodies are MessagePack, encrypted with the game's cipher; the channel opens on
    the first call and is reused.
    """

    def __init__(
        self,
        config: GrpcConfig,
        cipher: Cipher,
        *,
        secure: bool = True,
        timeout: float = TIMEOUT_SECONDS,
    ) -> None:
        self._config = config
        self.cipher = cipher
        self._secure = secure
        self._timeout = timeout
        self._channel: grpc.aio.Channel | None = None

    def _open(self) -> grpc.aio.Channel:
        if self._channel is None:
            if self._secure:
                self._channel = grpc.aio.secure_channel(
                    self._config.target, grpc.ssl_channel_credentials()
                )
            else:
                self._channel = grpc.aio.insecure_channel(self._config.target)
        return self._channel

    async def close(self) -> None:
        if self._channel is not None:
            await self._channel.close()
            self._channel = None

    async def call(self, method: str, request: Any = None) -> Any:
        """Call the service's ``method`` with ``request`` and return the decoded answer."""
        cipher = self.cipher
        rpc: grpc.aio.UnaryUnaryMultiCallable[Any, Any] = self._open().unary_unary(
            f"/{SERVICE}/{method}",
            request_serializer=lambda value: pack(value, cipher),
            response_deserializer=lambda data: unpack(data, cipher),
        )
        try:
            return await rpc(request, timeout=self._timeout)
        except grpc.aio.AioRpcError as exc:
            raise ServerError(
                f"{method} failed: {exc.code().name} {exc.details()}",
                retryable=exc.code() in _RETRYABLE,
            ) from exc
        except (ValueError, msgpack.UnpackException) as exc:
            raise ServerError(f"{method}: the answer was unreadable.") from exc

    async def check_asset_bundle(self, client_hash: str = "") -> BundleCheck:
        """Ask whether the game's asset bundles changed since ``client_hash``."""
        return BundleCheck.from_answer(await self.call("CheckAssetBundle", client_hash))


@dataclass(frozen=True, slots=True)
class BundleFile:
    """One file of an asset bundle directory."""

    url: str
    version: str


@dataclass(frozen=True, slots=True)
class BundleContext:
    """The files of one asset bundle directory (``#AssetContext.json``)."""

    asset_hash: str
    files: Mapping[str, BundleFile]  # by table name

    @classmethod
    def parse(cls, check: BundleCheck, cdn_url: str, data: object) -> Self:
        """The context from the parsed ``#AssetContext.json``."""
        if not isinstance(data, Mapping):
            raise DataSyncError("The bundle's asset context is not a JSON object.")
        base = f"{cdn_url.rstrip('/')}/{check.context}"
        files = {}
        for name, entry in data.items():
            if (
                isinstance(entry, Mapping)
                and isinstance(entry.get("file"), str)
                and entry["file"]
            ):
                files[str(name)] = BundleFile(
                    f"{base}/{entry['file'].lstrip('/')}", str(entry.get("version", ""))
                )
        return cls(check.asset_hash, files)

    def to_asset_context(self) -> AssetContext:
        """The same shape as the other games' ``a.json``, with full file URLs."""
        return AssetContext.from_json(
            {
                "version": self.asset_hash,
                "context": {
                    name: {"file": file.url, "version": file.version}
                    for name, file in self.files.items()
                },
            }
        )


def context_url(cdn_url: str, check: BundleCheck) -> str:
    """Where the asset context of a bundle check is on the CDN."""
    return f"{cdn_url.rstrip('/')}/{check.context}/%23AssetContext.json"


async def fetch_bundle_context(
    client: httpx.AsyncClient,
    config: GrpcConfig,
    check: BundleCheck,
    *,
    retry: RetryPolicy = DEFAULT_RETRY,
) -> BundleContext:
    """Download and parse the asset context a bundle check points to."""
    url = context_url(config.cdn_url, check)
    response = await fetch(client, url, retry=retry, error=DataSyncError)
    try:
        data = json.loads(response.content.decode("utf-8-sig"))
    except ValueError as exc:
        raise DataSyncError(f"{url} is not JSON.") from exc
    return BundleContext.parse(check, config.cdn_url, data)
