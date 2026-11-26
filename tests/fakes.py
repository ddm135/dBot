"""Stand-ins shared by the tests: fake services, Discord interactions, Play, and a gRPC server."""

import io
import zipfile
from types import SimpleNamespace

import grpc
import httpx

from games.api.crypto import Cipher
from games.api.magic_onion import pack, unpack
from games.api.stores import PlayDetails
from games.data.tables import LoadedTables
from games.registry import GAMES
from games.service import State


class FakeService:
    def __init__(self, tables):
        self.data = State(GAMES["SM"])
        self.set(tables)

    def set(self, tables):
        self.data.loaded_tables = LoadedTables(None, tables) if tables else None

    def get(self, key):
        return self.data


class Sent:
    def __init__(self):
        self.calls = []

    async def send(self, content=None, **kwargs):
        self.calls.append((content, kwargs))
        return SimpleNamespace(edit=lambda **k: None)


class Itr:
    def __init__(self, user_id=1):
        self.followup = Sent()
        self.user = SimpleNamespace(id=user_id, color=0)
        self.namespace = SimpleNamespace()
        self.responded = []
        self.response = SimpleNamespace(defer=self._defer, send_message=self._send)

    async def _defer(self, **kwargs):
        pass

    async def _send(self, content=None, **kwargs):
        self.responded.append((content, kwargs))

    @property
    def last(self):
        return self.followup.calls[-1]


def make_apk(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()


class FakePlay:
    def __init__(
        self, version="2.7.4", code=274, url="https://play.example/base_assets.apk"
    ):
        self.details_result = PlayDetails(version, code)
        self.url = url
        self.calls = []
        self.error = None

    async def details(self, package):
        self.calls.append(("details", package))
        if self.error:
            raise self.error
        return self.details_result

    async def split_url(self, package, version_code, split_name):
        self.calls.append(("split", version_code, split_name))
        return self.url


class Server:
    def __init__(self, apk: bytes):
        self.apk = apk
        self.requests = []

    def client(self):
        def handler(request):
            self.requests.append(str(request.url))
            return httpx.Response(200, content=self.apk)

        return httpx.AsyncClient(transport=httpx.MockTransport(handler))


KEY = b"0123456789abcdef0123456789abcdef"


CIPHER = Cipher(KEY)


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


async def serve_grpc(platform):
    server = grpc.aio.server()
    server.add_generic_rpc_handlers((platform,))
    port = server.add_insecure_port("localhost:0")
    await server.start()
    return server, port
