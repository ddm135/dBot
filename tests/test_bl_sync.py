import base64
import gzip
import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import httpx
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad

from games.crypto import Cipher
from games.decks import build_deck_index
from games.index import build_index
from games.manifest import Manifest
from games.registry import GAMES
from games.service import DataService

from .test_magic_onion import Platform, serve

FIXTURES = Path(__file__).parent / "fixtures" / "bl"
BL = GAMES["BL"]
HASH = "1BD6F945234171EBB2AD8EBA4BACB2EE"
ANSWER = {
    "IsCheckSkip": False,
    "AssetHash": HASH,
    "Context": f"/version/prod/asset/{HASH} ",
    "InvokeParams": [],
}


def encode_table(entries: list[dict], key: bytes) -> bytes:
    """The game's table format: gzip of base64 of AES-ECB of the JSON."""
    raw = AES.new(key, AES.MODE_ECB).encrypt(
        pad(json.dumps(entries).encode(), AES.block_size)
    )
    return gzip.compress(base64.b64encode(raw))


def locale_bin(key: bytes) -> bytes:
    def entry(code, text):
        return {"code": code, "koKR": text, "enUS": text}

    return encode_table(
        [
            entry(700001002, "Down to Earth"),
            entry(700002007, "Another Album"),
            entry(700004004, "Third"),
            entry(700004005, "Fourth"),
            entry(700005004, "Fifth"),
            entry(700006003, "Sixth"),
            entry(10800084, "TAEYANG"),
            entry(10104953, "TAEYANG"),
        ],
        key,
    )


class Cdn:
    def __init__(self, tables):
        self.tables = tables
        self.requests = []

    def __call__(self, request):
        path = request.url.path
        self.requests.append(path)
        base = f"/version/prod/asset/{HASH}/"
        if path == base + "%23AssetContext.json" or path == base + "#AssetContext.json":
            return httpx.Response(
                200,
                json={
                    name: {"file": f"Client/{name}.bin", "version": f"V-{name}"}
                    for name in self.tables
                },
            )
        name = path.removeprefix(base + "Client/").removesuffix(".bin")
        if path.startswith(base + "Client/") and name in self.tables:
            return httpx.Response(200, content=self.tables[name])
        return httpx.Response(404)


def group_bin(key: bytes) -> bytes:
    # GroupData was not sent for BL; this one names deck 1 after its artist.
    return encode_table([{"code": 1, "localeName": 10800084, "orderIndex": 1}], key)


def tables(key: bytes):
    return {
        "MusicData": (FIXTURES / "MusicData.bin").read_bytes(),
        "ArtistData": (FIXTURES / "ArtistData.bin").read_bytes(),
        "LocaleData": locale_bin(key),
        "GroupData": group_bin(key),
        "AlbumData": (FIXTURES / "AlbumData.bin").read_bytes(),
    }


# What the real MusicData and ArtistData fixtures are encrypted with.
KEY = b"WnFKN1v_gUcgmUVZnjjjGXGwk557zBSO"


async def make_service(tmp_path, cdn, port):
    game = replace(
        BL,
        grpc=replace(BL.grpc, target=f"localhost:{port}", secure=False),  # type: ignore[arg-type]
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(cdn))
    service = DataService(
        tmp_path,
        client=client,
        cipher=Cipher(KEY),
        play=None,
        games=[game],
    )
    service.get("BL").manifest = Manifest(
        {"ActiveVersion_Android": "1.0.9", "ServerUrl": "https://unused"}
    )
    return service, game, client


async def test_bl_tables_come_from_the_grpc_context_and_build_decks(tmp_path):
    # The real MusicData and ArtistData are encrypted with the gRPC key.
    real_key = KEY
    data = tables(real_key)
    music = Cipher(real_key).decode_table(data["MusicData"])
    assert len(music) == 78

    cdn = Cdn(data)
    server, port = await serve(Platform(ANSWER, cipher=Cipher(real_key)))
    service, game, client = await make_service(tmp_path, cdn, port)
    try:
        async with client:
            assert await service.sync_tables_game(game) is True
            loaded = service.get("BL").loaded_tables
            assert loaded is not None
            assert set(loaded.tables) == {
                "MusicData",
                "ArtistData",
                "LocaleData",
                "GroupData",
                "AlbumData",
            }
            assert loaded.assets.version == HASH

            # a.json keeps only the result, with full file URLs.
            stored = json.loads(
                (tmp_path / "dalcom" / "BL" / "a.json").read_text(encoding="utf-8")
            )
            assert stored["version"] == HASH
            assert stored["context"]["MusicData"]["file"].endswith(
                f"/version/prod/asset/{HASH}/Client/MusicData.bin"
            )

            titles = {"1002": "QUINTESSENCE"}  # as read from the string table
            index = build_deck_index(
                loaded.tables, game.timezone, album_decks=True, album_titles=titles
            )
            # Songs are split by album: one deck per album, plus the hidden song's group.
            albums = [d for d in index if d.code >= 1000]
            assert [d.code for d in albums] == [
                1001,
                1002,
                2001,
                2002,
                2003,
                3001,
                3002,
                3003,
                3004,
                4001,
                4002,
                4003,
                5001,
                5002,
            ]
            assert sum(len(d.songs) for d in index) == 78
            deck = index.decks[1001]
            assert len(deck.songs) == 10
            assert deck.name == "TAEYANG : Down to Earth"
            assert deck.label == "TAEYANG : Down to Earth"
            assert index.decks[1002].name == "TAEYANG : QUINTESSENCE"
            assert index.decks[1002].songs[0].album == "QUINTESSENCE"
            first = deck.songs[0]
            assert first.name == "VIBE (feat. Jimin of BTS)"  # from analyticsData
            assert first.album == "Down to Earth"
            # The release date is the album's (2023-04-24 JST), not a song's.
            assert first.release == date(2023, 4, 25)
            # The hidden song belongs to no album, so it stays in its group's deck.
            (hidden,) = [s for s in index.songs.values() if s.is_hidden]
            assert hidden.deck_code < 1000

            # Album art is named by the catalog key Image_Album_<albumCode>.
            built = build_index(game, loaded.tables)
            assert built is not None
            assert built.album_ref(first.code) == "Image_Album_1001"
            assert built.album_ref(hidden.code) is None  # no album, no art

            # Nothing changed on the server: the second sync downloads nothing.
            before = len(cdn.requests)
            assert await service.sync_tables_game(game) is True
            assert [p for p in cdn.requests[before:] if p.endswith(".bin")] == []
    finally:
        await service.close()
        await server.stop(None)


async def test_when_the_platform_server_is_down_the_stored_tables_are_used(tmp_path):
    real_key = KEY
    data = tables(real_key)
    cdn = Cdn(data)
    server, port = await serve(Platform(ANSWER, cipher=Cipher(real_key)))
    service, game, client = await make_service(tmp_path, cdn, port)
    try:
        async with client:
            assert await service.sync_tables_game(game) is True
            await server.stop(None)  # the platform server goes away
            service.get("BL").loaded_tables = None  # as after a restart
            assert await service.sync_tables_game(game) is True
            loaded = service.get("BL").loaded_tables
            assert loaded is not None and "MusicData" in loaded.tables
    finally:
        await service.close()
