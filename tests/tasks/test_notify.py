from datetime import date, datetime
from types import SimpleNamespace

import discord
import pytest

from db.bonus_pings import PingPreferences
from games.charts.song_stats import SongStatsStore
from games.index import Indexes
from games.registry import GAMES
from tasks import notify_bonus
from tasks.notify_bonus import NotifyBonus, deck_texts, due_kinds
from tests.data import MemoryStats, sample
from tests.fakes import FakeService

SM = GAMES["SM"]


class FakeUser:
    def __init__(self, fail=None):
        self.sent = []
        self.fail = fail

    async def send(
        self, content=None, *, embed=None, embeds=None, files=None, silent=None
    ):
        if self.fail:
            exc, self.fail = self.fail, None
            raise exc
        self.sent.append(
            SimpleNamespace(content=content, embed=embed, files=files, silent=silent)
        )

    @property
    def embeds(self):
        return [m.embed for m in self.sent if m.embed is not None]


class Response:
    status = 403
    reason = "Forbidden"


class NoImages:
    async def emblem(self, game, deck):
        return None


def make_bot(database, users, tmp_path):
    indexes = Indexes(FakeService(sample().as_tables()))
    return SimpleNamespace(
        db=database,
        indexes=indexes,
        get_user=users.get,
        images=NoImages(),
        stats=SongStatsStore(MemoryStats()),
    )


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    monkeypatch.setattr(notify_bonus, "SEND_DELAY", 0)


def at(hour, day=18):
    return datetime(2025, 9, day, hour, 10, tzinfo=SM.timezone)


def test_due_kinds():
    assert due_kinds(PingPreferences(1, 1), 23) == ["start", "end"]
    assert due_kinds(PingPreferences(1, 1), 22) == []
    assert due_kinds(PingPreferences(3, 0), 22) == ["start"]
    assert due_kinds(PingPreferences(0, 0), 23) == []


async def test_a_due_ping_is_a_header_then_one_embed_per_artist(database, tmp_path):
    user = FakeUser()
    bot = make_bot(database, {10: user}, tmp_path)
    await database.bonus_pings.subscribe(10, "SM", 1)
    cog = NotifyBonus(bot)

    assert await cog.notify_game(SM, at(22)) == 0  # not due yet
    assert await cog.notify_game(SM, at(23)) == 1
    header = user.sent[0].content
    assert header.startswith(f"## Bonus Reminder for {SM.name} on <t:")
    assert header.endswith(":f>")
    (embed,) = user.embeds
    assert embed.author.name == "TWICE" and embed.color.value == SM.color
    field = embed.fields[0]
    assert field.name.startswith("Available <t:") and field.name.endswith(
        ":green_circle:"
    )
    # Nayeon's birthday is on both songs of the deck: one line for all of them.
    assert (
        field.value == "> Nayeon - **All Songs**\n> 2% | September 19 - September 25\n"
    )
    assert user.sent[1].silent is True
    assert await cog.notify_game(SM, at(23)) == 0  # already sent
    assert len(user.sent) == 2


async def test_nothing_is_sent_to_other_decks_or_on_quiet_days(database, tmp_path):
    user = FakeUser()
    bot = make_bot(database, {10: user}, tmp_path)
    await database.bonus_pings.subscribe(10, "SM", 2)  # BTS has only hidden songs
    cog = NotifyBonus(bot)
    assert await cog.notify_game(SM, at(23)) == 0
    await database.bonus_pings.subscribe(10, "SM", 1)
    assert await cog.notify_game(SM, at(23, day=1)) == 0  # no events on Sep 2
    assert user.sent == []


async def test_earlier_preferences_and_missed_hours(database, tmp_path):
    early, normal = FakeUser(), FakeUser()
    bot = make_bot(database, {10: early, 20: normal}, tmp_path)
    await database.bonus_pings.subscribe(10, "SM", 1)
    await database.bonus_pings.subscribe(20, "SM", 1)
    await database.bonus_pings.set_preferences(10, start_hours=3)
    cog = NotifyBonus(bot)
    assert await cog.notify_game(SM, at(21)) == 1  # only the 3-hour user
    assert early.sent and not normal.sent
    assert await cog.notify_game(SM, at(23)) == 1  # the other, later
    assert normal.sent and len(early.sent) == 2  # early is not repeated


async def test_a_failed_send_is_retried_but_closed_dms_are_not(database, tmp_path):
    flaky = FakeUser(fail=discord.HTTPException(Response(), "boom"))
    closed = FakeUser(fail=discord.Forbidden(Response(), "no dms"))
    bot = make_bot(database, {10: flaky, 20: closed}, tmp_path)
    await database.bonus_pings.subscribe(10, "SM", 1)
    await database.bonus_pings.subscribe(20, "SM", 1)
    cog = NotifyBonus(bot)

    assert await cog.notify_game(SM, at(23)) == 1  # closed DMs count as handled
    assert flaky.sent == []
    assert await cog.notify_game(SM, at(23)) == 1  # flaky retried now
    assert len(flaky.sent) == 2 and closed.sent == []


async def test_end_pings_describe_what_ends(database, tmp_path):
    user = FakeUser()
    bot = make_bot(database, {10: user}, tmp_path)
    await database.bonus_pings.subscribe(10, "SM", 1)
    await database.bonus_pings.set_preferences(10, start_hours=0, end_hours=1)
    cog = NotifyBonus(bot)
    # Nayeon's window is Sep 19 - 25; the last day is Sep 25, so pinged on the 24th.
    assert await cog.notify_game(SM, at(23, day=24)) == 1
    (embed,) = user.embeds
    (field,) = embed.fields
    assert field.name.startswith("Ends <t:") and field.name.endswith(":orange_circle:")
    assert "Available" not in field.name


def test_deck_texts_only_has_the_requested_kinds():
    from games.bonus.notices import notices_for_day

    index = Indexes(FakeService(sample().as_tables())).get("SM")
    cal = Indexes(FakeService(sample().as_tables())).calendar("SM", 2025)
    plan = notices_for_day(index.decks.decks, cal.events_on(date(2025, 9, 19)), [1])
    assert set(deck_texts(index, 1, plan[1], ["start"], {})) == {"start"}
    assert deck_texts(index, 1, plan[1], ["end"], {}) == {}


async def test_a_long_ping_time_reaches_two_days_ahead_without_skipping_tomorrow(
    database, tmp_path
):
    user = FakeUser()
    bot = make_bot(database, {10: user}, tmp_path)
    await database.bonus_pings.subscribe(10, "SM", 1)
    await database.bonus_pings.set_preferences(10, start_hours=30, end_hours=0)
    cog = NotifyBonus(bot)

    assert await cog.notify_game(SM, at(17, day=17)) == 0  # 31 hours before Sep 19
    assert await cog.notify_game(SM, at(18, day=17)) == 1  # 30 hours before
    assert await cog.notify_game(SM, at(23, day=17)) == 0  # sent once
    assert await cog.notify_game(SM, at(0, day=18)) == 0  # still once, now tomorrow
    assert len(user.sent) == 2


async def test_changing_to_a_long_ping_time_still_sends_tomorrow(database, tmp_path):
    user = FakeUser()
    bot = make_bot(database, {10: user}, tmp_path)
    await database.bonus_pings.subscribe(10, "SM", 1)
    await database.bonus_pings.set_preferences(10, start_hours=47, end_hours=0)
    cog = NotifyBonus(bot)
    # The 47-hour mark for Sep 19 passed long ago: it goes out at the next run.
    assert await cog.notify_game(SM, at(9, day=18)) == 1


async def test_run_all_looks_at_every_game_with_bonuses(database, tmp_path):
    bot = make_bot(database, {}, tmp_path)
    bot.games = [SimpleNamespace(game=SM)]
    cog = NotifyBonus(bot)
    seen = []

    async def record(game, now):
        seen.append(game.key)
        return 0

    cog.notify_game = record
    await cog.run_all()
    await cog.run_all()  # the startup run and the hourly one can follow each other
    assert seen == ["SM", "SM"]
