from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import discord

from pinata.config import CHANNELS, PRIZES, Prize
from pinata.lottery import (
    MIN_ROLL_OTHER,
    MIN_ROLL_SUPERSTAR,
    Draw,
    Entries,
    draw,
    min_roll,
)
from tasks import pinata as pinata_task
from tasks.pinata import Pinata, day_key
from ui.pinata import BoxView, box_embed, result_embed


class Rolls:
    """A random source that gives these numbers (as hundredths) in turn."""

    def __init__(self, *hundredths):
        self.values = list(hundredths)

    def randint(self, low, high):
        assert (low, high) == (0, 10_000)
        return self.values.pop(0)


class Person:
    def __init__(self, name):
        self.name = name
        self.mention = f"<@{name}>"

    def __repr__(self):
        return self.name


A, B, C = Person("a"), Person("b"), Person("c")


def test_the_prizes_are_listed_for_the_event_days_only():
    assert sorted(PRIZES) == ["0401", "0403", "0404", "0405", "0406", "0407"]
    assert PRIZES["0407"] == (Prize("全民天团", ""),)
    assert PRIZES["0403"][0] == Prize("IZ\\*ONE", "SUPERSTAR")
    assert len(CHANNELS) == 2


def test_the_day_is_the_day_in_korea():
    assert day_key(datetime(2026, 3, 31, 14, 59, tzinfo=UTC)) == "0331"
    assert day_key(datetime(2026, 3, 31, 15, 0, tzinfo=UTC)) == "0401"


def test_lining_up():
    entries: Entries[Person] = Entries(3)
    assert not entries
    entries.join_all(A)
    entries.toggle(B, 1)
    entries.toggle(C, 1)
    entries.toggle(A, 1)  # A leaves the second line only
    assert entries.for_prize(0) == [A]
    assert entries.for_prize(1) == [B, C]
    assert next(iter(entries)) == (A, [True, False, True])
    entries.toggle(B, 1)  # no lines left: not in the box at all
    entries.leave_all(C)
    entries.leave_all(C)  # leaving twice is fine
    assert [who for who, _ in entries] == [A]


def test_the_minimum_depends_on_the_kind_of_prize():
    assert min_roll(True) == MIN_ROLL_SUPERSTAR == 99.5
    assert min_roll(False) == MIN_ROLL_OTHER == 99.99


def test_the_first_to_reach_the_minimum_wins():
    result = draw([A, B, C], 99.5, Rolls(5000, 9950, 10000))
    assert result.rolls == ((A, 50.0), (B, 99.5), (C, 100.0))
    assert result.winner is B
    assert result.rolls_needed == 0


def test_with_no_winner_it_counts_the_rolls_it_would_have_taken():
    result = draw([A], 99.99, Rolls(1, 2, 3, 9999))
    assert result.winner is None
    assert result.rolls_needed == 3  # 0.02, 0.03 and then 99.99
    empty = draw([], 99.5, Rolls(9950))
    assert empty.rolls == () and empty.rolls_needed == 1


def test_the_box_embed_shows_prizes_and_the_line():
    entries: Entries[Person] = Entries(2)
    colour = discord.Colour(0xFF0000)
    embed = box_embed(["SuperStar BTS", "<@&5>"], colour, entries)
    assert embed.description == (
        "Inside this box:\n**SuperStar BTS\n<@&5>\n**\nLining Up:\nNone"
    )
    assert embed.colour == colour
    entries.join_all(A)
    entries.toggle(B, 1)
    embed = box_embed(["x", "y"], None, entries)
    assert embed.description.endswith("Lining Up:\n◼◼ 1. <@a>\n◻◼ 2. <@b>\n")
    assert embed.footer.icon_url == "attachment://guitar.png"


def test_a_result_strikes_through_everyone_after_the_winner():
    result: Draw[Person] = Draw(((A, 10.0), (B, 99.6), (C, 99.7)), B, 99.5, 0)
    embed = result_embed(result, "**BTS**", None, nobody_joined=False)
    assert embed.description == (
        "<@b> opened the box and got ****BTS****\n\n"
        "Attendees:\n`10.0` <@a>\n**`99.6` <@b>**~~\n**`99.7` <@c>**\n~~"
    )
    assert embed.footer.text == "Need to get 99.5 or higher to win"


def test_a_result_without_a_winner_says_how_many_rolls_it_needed():
    result: Draw[Person] = Draw(((A, 10.0),), None, 99.99, 12)
    embed = result_embed(result, "YG", None, nobody_joined=False)
    assert embed.description == (
        "**12** more rolls were needed to get a winner for **YG**\n\n"
        "Attendees:\n`10.0` <@a>\n"
    )
    nobody: Draw[Person] = Draw((), None, 99.99, 4)
    assert result_embed(nobody, "YG", None, nobody_joined=True).description.endswith(
        "Attendees:\nNone"
    )


class Click:
    def __init__(self, user):
        self.user = user
        self.edited = []
        self.response = SimpleNamespace(edit_message=self._edit)

    async def _edit(self, embed):
        self.edited.append(embed)


async def test_the_buttons_line_people_up_and_refresh_the_box():
    entries: Entries[Person] = Entries(2)
    renders = []

    def render():
        renders.append([who for who, _ in entries])
        return "embed"

    view = BoxView(["one", "two"], entries, render, timeout=5)
    labels = [b.label for b in view.children]
    assert labels == ["Join All", "one", "two", "Leave All"]
    join, _one, two, leave = view.children
    click = Click(A)
    await join.callback(click)
    await two.callback(Click(B))
    assert entries.for_prize(0) == [A]
    assert entries.for_prize(1) == [A, B]
    await leave.callback(click)
    assert entries.for_prize(1) == [B]
    assert click.edited == ["embed", "embed"]
    assert renders[-1] == [B]
    view.close()
    assert all(b.disabled for b in view.children)


class Channel:
    def __init__(self, guild):
        self.guild = guild
        self.sent = []
        self.message = SimpleNamespace(edits=[])

        async def edit(**kwargs):
            self.message.edits.append(kwargs)

        self.message.edit = edit

    async def send(self, text=None, **kwargs):
        self.sent.append((text, kwargs))
        return self.message


def make_guild(roles):
    return SimpleNamespace(id=1, get_role=roles.get)


def role(role_id, name):
    return SimpleNamespace(
        id=role_id, name=name, mention=f"<@&{role_id}>", colour=discord.Colour(0x00FF00)
    )


def member(user_id, name):
    who = MagicMock(spec=discord.Member)
    who.id, who.mention = user_id, f"<@{user_id}>"
    who.__hash__ = lambda self: user_id
    return who


class Roles:
    def __init__(self):
        self.added = []

    async def add(self, user_id, role_ids):
        self.added.append((user_id, list(role_ids)))


def make_cog(monkeypatch, channel, rolls, superstar_roles=()):
    async def find(bot, channel_id, kind):
        return channel

    monkeypatch.setattr(pinata_task, "find_channel", find)
    monkeypatch.setattr(pinata_task, "SUPERSTAR_ROLES", {1: tuple(superstar_roles)})
    bot = SimpleNamespace(db=SimpleNamespace(roles=Roles()))
    return Pinata(bot, window=0, rng=Rolls(*rolls)), bot


async def test_a_box_is_opened_drawn_and_won_roles_are_stored_or_given(monkeypatch):
    stored, plain = role(10, "Stored"), role(11, "Plain")
    channel = Channel(make_guild({10: stored, 11: plain}))
    prizes = (Prize(10, "SuperStar"), Prize(11), Prize("Text", "SUPERSTAR"))
    cog, bot = make_cog(
        monkeypatch,
        channel,
        # prize 0 (99.5): only x is in line and rolls 99.5, a win
        # prize 1 (99.99): x rolls 10, y rolls 100 and wins
        # prize 2: only x is in line and rolls 0.05; 2 more rolls to get 99.99
        [9950, 1000, 10000, 5, 6, 9999],
        superstar_roles=[10],
    )
    x, y = member(7, "x"), member(8, "y")

    original_sleep = pinata_task.asyncio.sleep

    async def sleeper(seconds):
        view = channel.sent[0][1]["view"]
        join, _first, second, third, _leave = view.children
        await join.callback(Click(x))
        await second.callback(Click(y))
        await third.callback(Click(y))  # y toggles prize 3 on...
        await third.callback(Click(y))  # ...and off again
        await original_sleep(0)

    monkeypatch.setattr(pinata_task.asyncio, "sleep", sleeper)
    await cog.open_in(1, 2, prizes)

    first_post = channel.sent[0]
    assert first_post[1]["embed"].description.startswith(
        "Inside this box:\n**SuperStar <@&10>\n<@&11>\nSUPERSTAR Text\n**"
    )
    assert channel.message.edits  # the buttons were switched off
    descriptions = [
        s[1]["embed"].description for s in channel.sent[1:] if "embed" in s[1]
    ]
    assert "<@7> opened the box and got **SuperStar <@&10>**" in descriptions[0]
    assert "<@8> opened the box and got **<@&11>**" in descriptions[1]
    assert "**2** more rolls were needed" in descriptions[2]
    texts = [s[0] for s in channel.sent if s[0]]
    assert texts[0].endswith("The role has been added to your inventory.")
    assert bot.db.roles.added == [(7, [10])]
    assert "added to your profile" in texts[1]
    y.add_roles.assert_awaited_once_with(plain)


async def test_a_box_without_a_reachable_channel_does_nothing(monkeypatch):
    cog, _ = make_cog(monkeypatch, None, [])

    async def none(bot, channel_id, kind):
        return None

    monkeypatch.setattr(pinata_task, "find_channel", none)
    await cog.open_in(1, 2, (Prize("A"),))


async def test_a_role_that_cannot_be_given_is_reported(monkeypatch):
    plain = role(11, "Plain")
    channel = Channel(make_guild({11: plain}))
    cog, _ = make_cog(monkeypatch, channel, [10000])
    x = member(7, "x")
    x.add_roles.side_effect = discord.Forbidden(
        SimpleNamespace(status=403, reason=""), "no"
    )

    async def sleeper(seconds):
        view = channel.sent[0][1]["view"]
        await view.children[0].callback(Click(x))

    monkeypatch.setattr(pinata_task.asyncio, "sleep", sleeper)
    await cog.open_in(1, 2, (Prize(11),))
    assert channel.sent[-1][0].endswith(
        "I could not give you the role; ask a moderator."
    )
