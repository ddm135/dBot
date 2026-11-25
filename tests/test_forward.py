import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import discord
import httpx
import pytest

from games.api.manifest import Manifest
from games.bonus.schedule import next_update
from games.models import ForwardConfig
from games.registry import GAMES
from games.service import DataService
from tasks import forward_update
from tasks.forward_update import ForwardUpdate, announcement

from .data import KST, NO_RETRY

SM = GAMES["SM"]
NOW = datetime(2026, 11, 24, 12, 0, tzinfo=KST)


def ms(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


# --- which update is coming ---------------------------------------------------


def test_the_earliest_song_within_a_week_is_the_next_update():
    tables = {
        "MusicData": {
            "1": {"displayStartAt": ms(NOW - timedelta(days=1))},  # already out
            "2": {"displayStartAt": ms(NOW + timedelta(days=5))},
            "3": {"displayStartAt": ms(NOW + timedelta(days=2))},
            "4": {"displayStartAt": ms(NOW + timedelta(days=8))},  # too far
            "5": {},
        },
        "GroupData": {"9": {"displayStartAt": ms(NOW + timedelta(days=1))}},
    }
    assert next_update(tables, KST, NOW) == NOW + timedelta(days=2)


def test_groups_count_only_when_no_song_is_coming():
    tables = {
        "MusicData": {"1": {"displayStartAt": ms(NOW + timedelta(days=30))}},
        "GroupData": {"9": {"displayStartAt": ms(NOW + timedelta(days=1))}},
    }
    assert next_update(tables, KST, NOW) == NOW + timedelta(days=1)


def test_nothing_is_coming_and_junk_is_ignored():
    assert next_update({}, KST, NOW) is None
    junk = {
        "MusicData": {
            "1": {"displayStartAt": "soon"},
            "2": {"displayStartAt": True},
            "3": {"displayStartAt": -5},
            "4": {"displayStartAt": 1e30},
            "5": "x",
        }
    }
    assert next_update(junk, KST, NOW) is None
    # Exactly now is not "coming"; exactly a week away is.
    edge = {"MusicData": {"1": {"displayStartAt": ms(NOW)}}}
    assert next_update(edge, KST, NOW) is None
    week = {"MusicData": {"1": {"displayStartAt": ms(NOW + timedelta(days=7))}}}
    assert next_update(week, KST, NOW) == NOW + timedelta(days=7)


def test_the_start_is_in_the_games_timezone():
    start = next_update(
        {"MusicData": {"1": {"displayStartAt": ms(NOW + timedelta(days=1))}}}, KST, NOW
    )
    assert start is not None and start.tzinfo is KST


# --- is_online -----------------------------------------------------------------


class Cipher:
    def encrypt_cbc(self, text, iv):
        return text

    def decrypt_cbc(self, text, iv):
        return text


def service(handler, game=SM):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    svc = DataService(
        Path("."),
        client=client,
        cipher=Cipher(),  # type: ignore[arg-type]
        play=None,
        games=[game],
        retry=NO_RETRY,
    )
    return svc, client


def make_handler(*, maintenance=False, code=1000, manifest_status=200):
    def handler(request):
        if request.url.host == "server.test":
            return httpx.Response(200, json={"code": code})
        if manifest_status != 200:
            return httpx.Response(manifest_status)
        return httpx.Response(
            200,
            json={
                "ActiveVersion_Android": SM.version_floor,
                "ServerUrl": "https://server.test/api",
                "MaintenanceUrl": "https://maint.test" if maintenance else "",
            },
        )

    return handler


async def test_a_game_is_online_when_not_in_maintenance_and_the_server_answers():
    svc, client = service(make_handler())
    async with client:
        assert await svc.is_online(SM) is True


async def test_maintenance_the_server_code_and_failures_all_mean_offline():
    for kwargs in (
        {"maintenance": True},
        {"code": 9999},
        {"manifest_status": 404},
        {"manifest_status": 503},
    ):
        svc, client = service(make_handler(**kwargs))
        async with client:
            assert await svc.is_online(SM) is False, kwargs

    def down(request):
        raise httpx.ConnectError("down")

    svc, client = service(down)
    async with client:
        assert await svc.is_online(SM) is False


# --- the cog -------------------------------------------------------------------


class FakeMessage:
    def __init__(self, content, fail_for=()):
        self.content = content
        self.forwarded = []
        self.fail_for = fail_for

    async def forward(self, channel):
        if channel.id in self.fail_for:
            raise discord.HTTPException(SimpleNamespace(status=403, reason="x"), "no")
        self.forwarded.append(channel.id)


class FakeChannel(discord.TextChannel):
    def __init__(self, channel_id, messages=()):
        self.id = channel_id
        self.messages = list(messages)
        self.sent = []
        self.purged = False

    async def send(self, content):
        self.sent.append(content)

    async def purge(self):
        self.purged = True
        self.messages.clear()
        return []

    def history(self, *, after=None, oldest_first=None):
        async def gen():
            for message in list(self.messages):
                yield message

        return gen()


class FakeGames:
    def __init__(self, manifest=None, tables=None, online=()):
        self.data = SimpleNamespace(game=SM, manifest=manifest, tables=tables or {})
        self.online = list(online)
        self.checks = 0

    def get(self, key):
        return self.data

    def __iter__(self):
        return iter([self.data])

    async def wait_until_ready(self):
        pass

    async def is_online(self, game):
        self.checks += 1
        return self.online.pop(0) if self.online else True


def manifest(maintenance=False):
    return Manifest(
        {
            "ActiveVersion_Android": "1.0.0",
            "MaintenanceUrl": "https://m" if maintenance else "",
        }
    )


def make_cog(games, channels):
    async def fetch_channel(channel_id):
        if channel_id not in channels:
            raise discord.NotFound(SimpleNamespace(status=404, reason="x"), "gone")
        return channels[channel_id]

    bot = SimpleNamespace(
        games=games, get_channel=channels.get, fetch_channel=fetch_channel
    )
    return ForwardUpdate(bot)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def fast_polling(monkeypatch):
    monkeypatch.setattr(forward_update, "POLL_SECONDS", 0)


async def test_maintenance_is_waited_out_then_forwarded_and_cleared():
    forward = SM.forward
    assert forward is not None
    source = FakeChannel(
        forward.maintenance_channel_id,
        [FakeMessage("one"), FakeMessage("two", fail_for={222})],
    )
    targets = {
        channel_id: FakeChannel(channel_id)
        for channel_id in (*forward.targets.values(), 222)
    }
    channels = {source.id: source, **{c: t for c, t in targets.items()}}
    games = FakeGames(manifest(maintenance=True), online=[False, False, True])
    cog = make_cog(games, channels)

    assert cog.plan(SM) is True
    assert cog.plan(SM) is False  # one wait per game
    await asyncio.gather(*cog.queue.values())

    assert games.checks == 3
    assert source.purged
    assert source.messages == []
    assert cog.queue == {}  # nothing left waiting


async def test_messages_reach_every_target_oldest_first_and_failures_are_skipped():
    forward = SM.forward
    assert forward is not None
    one, two = FakeMessage("one"), FakeMessage("two")
    source = FakeChannel(forward.maintenance_channel_id, [one, two])
    ids = list(forward.targets.values())
    channels = {source.id: source, **{c: FakeChannel(c) for c in ids}}
    one.fail_for = {ids[0]}
    cog = make_cog(FakeGames(manifest()), channels)

    assert await cog._forward(SM, source.id) == 2
    assert one.forwarded == ids[1:]  # the failing target was skipped
    assert two.forwarded == ids
    assert source.purged


async def test_nothing_is_purged_when_no_target_can_be_reached():
    forward = SM.forward
    assert forward is not None
    source = FakeChannel(forward.maintenance_channel_id, [FakeMessage("keep me")])
    cog = make_cog(FakeGames(manifest()), {source.id: source})
    assert await cog._forward(SM, source.id) == 0
    assert not source.purged and len(source.messages) == 1
    # An unreachable source is just as harmless.
    assert await make_cog(FakeGames(manifest()), {})._forward(SM, 5) == 0


async def test_an_upcoming_update_is_announced_once_then_awaited():
    forward = SM.forward
    assert forward is not None
    start = datetime.now(tz=SM.timezone) + timedelta(seconds=0.05)
    tables = {"MusicData": {"1": {"displayStartAt": ms(start)}}}
    source_id = forward.source_channel_id(scheduled=True)
    source = FakeChannel(source_id, [FakeMessage("news")])
    notice = FakeChannel(forward_update.NEXT_UPDATE_CHANNEL_ID)
    ids = list(forward.targets.values())
    channels = {
        source.id: source,
        notice.id: notice,
        **{c: FakeChannel(c) for c in ids},
    }
    cog = make_cog(FakeGames(manifest(), tables), channels)

    assert cog.plan(SM) is True
    await asyncio.gather(*cog.queue.values())
    text = announcement(SM, source_id, start.replace(microsecond=0))
    assert len(notice.sent) == 1
    assert notice.sent[0].startswith(
        f"{SM.name}: Forwarding from <#{source_id}> on <t:"
    )
    assert text.split(" on ")[0] == notice.sent[0].split(" on ")[0]
    assert source.purged

    # Announced already: a second run does not repeat it.
    notice.messages.append(FakeMessage(notice.sent[0]))
    await cog._announce(
        SM,
        source_id,
        datetime.fromtimestamp(
            int(notice.sent[0].split("<t:")[1].split(":")[0]), tz=SM.timezone
        ),
    )
    assert len(notice.sent) == 1


async def test_nothing_is_planned_without_news_or_config(monkeypatch):
    cog = make_cog(FakeGames(manifest()), {})
    assert cog.plan(SM) is False  # online and no update coming
    assert make_cog(FakeGames(None), {}).plan(SM) is False  # no manifest yet
    bare = SimpleNamespace(key="X", forward=None)
    assert cog.plan(bare) is False  # type: ignore[arg-type]
    assert cog.queue == {}


async def test_a_crashed_wait_is_logged_and_does_not_block_the_game(caplog):
    games = FakeGames(manifest(maintenance=True))

    async def broken(game):
        raise RuntimeError("boom")

    games.is_online = broken  # type: ignore[method-assign]
    cog = make_cog(games, {})
    with caplog.at_level(logging.ERROR):
        assert cog.plan(SM)
        await asyncio.gather(*cog.queue.values(), return_exceptions=True)
        await asyncio.sleep(0)
    assert "Forwarding failed" in caplog.text
    assert cog.queue == {}
    assert cog.plan(SM) is True  # tried again at the next hour
    await cog.cog_unload()
    assert cog.queue == {}


def test_every_game_with_forwarding_has_targets():
    for game in GAMES.values():
        if game.forward is not None:
            assert isinstance(game.forward, ForwardConfig)
            assert game.forward.targets
