"""Pings users before bonuses they follow start or end."""

import asyncio
import logging
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import discord

from db.bonus_pings import PingKind, PingPreferences
from games.bonus.notices import (
    Category,
    NoticeLine,
    Section,
    hours_due,
    notices_for_day,
)
from games.charts.song_stats import SongStat
from games.index import Index
from games.models import Game
from ui.bonus import midnight, notice_embed, notice_text
from ui.images import Upload, files, prepare
from ui.text import timestamp

from .hourly import HourlyTask

if TYPE_CHECKING:
    from bot import dBot
    from games.service import State

logger = logging.getLogger(__name__)

MAX_DAYS_AHEAD = 2  # a ping time is at most 47 hours before a day
SEND_DELAY = 0.5  # between DMs, to stay clear of rate limits


def due_kinds(prefs: PingPreferences, hour: int, days_ahead: int = 1) -> list[Category]:
    """Which kinds of ping are due at a local hour for a day ``days_ahead`` away."""
    kinds: list[Category] = []
    if hours_due(hour, prefs.start_hours, days_ahead):
        kinds.append("start")
    if hours_due(hour, prefs.end_hours, days_ahead):
        kinds.append("end")
    return kinds


def deck_texts(
    index: Index,
    deck_code: int,
    lines: dict[Category, list[NoticeLine]],
    kinds: list[Category],
    stats: dict[int, SongStat],
) -> dict[Section, list[str]]:
    """The entries of one deck's ping, as block-quote text, by section."""
    deck = index.decks.decks[deck_code]
    texts: dict[Section, list[str]] = {}
    for kind in kinds:
        for line in lines[kind]:
            if text := notice_text(line, deck, stats):
                texts.setdefault(line.section, []).append(text)
    return texts


class NotifyBonus(HourlyTask):
    minute = 0
    skip_when_running = False  # the hourly run and the first one follow each other
    failure = "Bonus pings failed."

    def games(self) -> Iterable[State]:
        return (data for data in self.bot.games if data.game.has_bonuses)

    async def run_game(self, data: State) -> None:
        await self.notify_game(data.game, data.game.now())

    async def finish(self) -> None:
        await self.bot.db.bonus_pings.prune(datetime.now(UTC).date())

    async def notify_game(self, game: Game, now: datetime) -> int:
        """Send the pings that are due at ``now``. Returns how many were sent.

        Settings reach two days ahead (up to 47 hours), so tomorrow and the day
        after are both looked at; a setting of 24 hours or more is due for
        tomorrow at once, so changing it never skips tomorrow's bonuses.
        """
        sent = 0
        for days_ahead in range(1, MAX_DAYS_AHEAD + 1):
            sent += await self._notify_day(game, now, days_ahead)
        return sent

    async def _notify_day(self, game: Game, now: datetime, days_ahead: int) -> int:
        target = now.date() + timedelta(days=days_ahead)
        await self.bot.indexes.warm(game.key, target.year)  # off the event loop
        index = self.bot.indexes.get(game.key)
        calendar = self.bot.indexes.calendar(game.key, target.year)
        if index is None or calendar is None:
            return 0
        subscribers = await self.bot.db.bonus_pings.subscribers(game.key)
        if not subscribers:
            return 0

        events = calendar.events_on(target)
        if not events:
            return 0
        prefs = await self.bot.db.bonus_pings.preferences(list(subscribers))
        stats = dict(await self.bot.stats.get(game.key))

        sent = 0
        for user_id, decks in subscribers.items():
            plan = notices_for_day(index.decks.decks, events, decks)
            if not plan:
                continue
            kinds: list[Category] = []
            for kind in due_kinds(prefs[user_id], now.hour, days_ahead):
                has_lines = any(lines[kind] for lines in plan.values())
                if has_lines and await self.bot.db.bonus_pings.claim(
                    user_id, game.key, target, _ping_kind(kind)
                ):
                    kinds.append(kind)
            if not kinds:
                continue
            if await self._send(user_id, game, index, target, kinds, plan, stats):
                sent += 1
            else:  # let the next hour try again
                for kind in kinds:
                    await self.bot.db.bonus_pings.release(
                        user_id, game.key, target, _ping_kind(kind)
                    )
            await asyncio.sleep(SEND_DELAY)
        return sent

    async def _send(
        self,
        user_id: int,
        game: Game,
        index: Index,
        day: date,
        kinds: list[Category],
        plan: dict[int, dict[Category, list[NoticeLine]]],
        stats: dict[int, SongStat],
    ) -> bool:
        posts: list[tuple[discord.Embed, list[Upload]]] = []
        for code in sorted(plan, key=lambda c: index.group_name(c) or ""):
            texts = deck_texts(index, code, plan[code], kinds, stats)
            if not texts:
                continue
            emblem = await self.bot.images.emblem(game.key, code)
            icon, uploads = prepare(emblem, None, "icon")
            posts.append(
                (
                    notice_embed(index, index.decks.decks[code], day, texts, icon),
                    uploads,
                )
            )
        if not posts:
            return True

        header = f"## Bonus Reminder for {game.name} on {timestamp(midnight(index, day), 'f')}"
        try:
            user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            await user.send(header)
            for embed, uploads in posts:
                await user.send(embed=embed, files=files(uploads), silent=True)
        except discord.Forbidden, discord.NotFound:
            return True  # DMs closed or user gone: retrying will not help
        except discord.HTTPException:
            logger.warning("Could not send a bonus ping to %d.", user_id, exc_info=True)
            return False
        return True


def _ping_kind(category: Category) -> PingKind:
    return category


async def setup(bot: dBot) -> None:
    await bot.add_cog(NotifyBonus(bot))
