import json

import grpc
import grpc.aio
import httpx
import msgpack
import pytest

from games.crypto import Cipher, CryptoError
from games.errors import DataSyncError, ServerError
from games.magic_onion import (
    BundleCheck,
    BundleContext,
    MagicOnionClient,
    context_url,
    fetch_bundle_context,
    pack,
    unpack,
)
from games.models import GrpcConfig
from games.registry import GAMES

KEY = b"0123456789abcdef0123456789abcdef"
CIPHER = Cipher(KEY)
ANSWER = {
    "IsCheckSkip": False,
    "AssetHash": "1BD6",
    "Context": "/version/prod/asset/1BD6 ",
    "InvokeParams": [],
}

from .data import NO_RETRY


def config(target="localhost:1"):
    return GrpcConfig(target=target, cdn_url="https://cdn.test/")


def test_bodies_are_msgpack_inside_iv_prefixed_aes_cbc():
    body = pack({"a": [1, "x"]}, CIPHER)
    assert len(body) % 16 == 0 and len(body) >= 32
    assert pack({"a": [1, "x"]}, CIPHER) != body  # a fresh IV every time
    assert unpack(body, CIPHER) == {"a": [1, "x"]}
    assert msgpack.unpackb(CIPHER.unseal(body), raw=False) == {"a": [1, "x"]}
    assert unpack(b"", CIPHER) is None
    for bad in (b"short", b"x" * 33):
        with pytest.raises(CryptoError):
            CIPHER.unseal(bad)
    assert CIPHER.unseal(CIPHER.seal(b"")) == b""


def test_the_check_answer_is_validated_and_the_path_cleaned():
    check = BundleCheck.from_answer(ANSWER)
    assert check == BundleCheck("1BD6", "version/prod/asset/1BD6", False)
    assert BundleCheck.from_answer({**ANSWER, "IsCheckSkip": True}).skip
    for bad in ("x", {}, {"AssetHash": "a", "Context": " / "}, {"AssetHash": 1}):
        with pytest.raises(ServerError):
            BundleCheck.from_answer(bad)


def test_the_context_url_matches_what_the_game_uses():
    check = BundleCheck.from_answer(ANSWER)
    assert context_url("https://cdn.test/", check) == (
        "https://cdn.test/version/prod/asset/1BD6/%23AssetContext.json"
    )


def test_context_files_become_urls_and_junk_entries_are_dropped():
    check = BundleCheck.from_answer(ANSWER)
    context = BundleContext.parse(
        check,
        "https://cdn.test",
        {
            "MusicData": {"file": "Client/MusicData.bin", "version": "AA"},
            "Empty": {"file": ""},
            "Bad": 3,
        },
    )
    assert set(context.files) == {"MusicData"}
    music = context.files["MusicData"]
    assert music.url == "https://cdn.test/version/prod/asset/1BD6/Client/MusicData.bin"
    assert music.version == "AA"
    with pytest.raises(DataSyncError):
        BundleContext.parse(check, "https://cdn.test", [])


async def test_the_context_is_downloaded_with_a_bom_and_errors_are_reported():
    check = BundleCheck.from_answer(ANSWER)
    body = json.dumps({"MusicData": {"file": "Client/MusicData.bin", "version": "1"}})
    seen = []

    def handler(request):
        seen.append(str(request.url))
        if "bad" in request.url.path:
            return httpx.Response(404)
        return httpx.Response(200, content=b"\xef\xbb\xbf" + body.encode())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        got = await fetch_bundle_context(client, config(), check, retry=NO_RETRY)
        assert "MusicData" in got.files
        assert seen == ["https://cdn.test/version/prod/asset/1BD6/%23AssetContext.json"]
        with pytest.raises(DataSyncError):
            await fetch_bundle_context(
                client,
                config(),
                BundleCheck("x", "bad/path", False),
                retry=NO_RETRY,
            )


async def test_garbage_is_not_json():
    check = BundleCheck.from_answer(ANSWER)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"<html>"))
    ) as client:
        with pytest.raises(DataSyncError):
            await fetch_bundle_context(client, config(), check, retry=NO_RETRY)


class Platform(grpc.GenericRpcHandler):
    """A stand-in server that speaks the game's wire format."""

    def __init__(self, answer=None, fail=None, cipher=CIPHER):
        self.cipher = cipher
        self.requests = []
        self.metadata = []
        self.answer = answer
        self.fail = fail

    def service(self, details):
        if details.method != "/IPlatform/CheckAssetBundle":
            return None

        async def handle(request, context):
            self.requests.append(unpack(request, self.cipher))
            self.metadata.append(dict(context.invocation_metadata()))
            if self.fail:
                await context.abort(self.fail, "nope")
            return pack(self.answer, self.cipher)

        return grpc.unary_unary_rpc_method_handler(handle)


async def serve(platform):
    server = grpc.aio.server()
    server.add_generic_rpc_handlers((platform,))
    port = server.add_insecure_port("localhost:0")
    await server.start()
    return server, port


async def test_check_asset_bundle_over_a_real_grpc_channel():
    platform = Platform(ANSWER)
    server, port = await serve(platform)
    client = MagicOnionClient(config(f"localhost:{port}"), CIPHER, secure=False)
    try:
        check = await client.check_asset_bundle()
        assert check.asset_hash == "1BD6" and check.context.endswith("1BD6")
        assert platform.requests == [""]  # the client hash
        await client.check_asset_bundle("abc")
        assert platform.requests[-1] == "abc"
    finally:
        await client.close()
        await server.stop(None)


@pytest.mark.parametrize(
    ("status", "retryable"),
    [
        (grpc.StatusCode.UNAVAILABLE, True),
        (grpc.StatusCode.PERMISSION_DENIED, False),
    ],
)
async def test_rpc_failures_become_game_server_errors(status, retryable):
    server, port = await serve(Platform(fail=status))
    client = MagicOnionClient(config(f"localhost:{port}"), CIPHER, secure=False)
    try:
        with pytest.raises(ServerError) as caught:
            await client.check_asset_bundle()
        assert caught.value.retryable is retryable
    finally:
        await client.close()
        await server.stop(None)


async def test_an_unreadable_answer_is_an_error_not_a_crash():
    class Broken(Platform):
        def service(self, details):
            async def handle(request, context):
                return b"not encrypted at all"

            return grpc.unary_unary_rpc_method_handler(handle)

    server, port = await serve(Broken())
    client = MagicOnionClient(config(f"localhost:{port}"), CIPHER, secure=False)
    try:
        with pytest.raises(ServerError):
            await client.check_asset_bundle()
    finally:
        await client.close()
        await server.stop(None)


async def test_an_unreachable_server_is_retryable():
    client = MagicOnionClient(config("localhost:1"), CIPHER, secure=False, timeout=2)
    try:
        with pytest.raises(ServerError) as caught:
            await client.check_asset_bundle()
        assert caught.value.retryable
    finally:
        await client.close()


def test_bl_is_configured_for_grpc():
    bl = GAMES["BL"]
    assert bl.grpc is not None and bl.grpc.target == "ssbl.dalcomsoft.net:443"
    assert all(g.grpc is None for k, g in GAMES.items() if k != "BL")
