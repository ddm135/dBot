"""Forwards the maintenance and update notices to the servers once a game is back."""

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

import discord

from channels import find_channel
from discord_ids import NEXT_UPDATE_CHANNEL_ID
from games.bonus.schedule import WINDOW, next_update
from games.models import Game

from .hourly import HourlyTask

if TYPE_CHECKING:
    from bot import dBot
    from games.service import State

logger = logging.getLogger(__name__)

POLL_SECONDS = 60


def announcement(game: Game, source_id: int, start: datetime) -> str:
    return (
        f"{game.name}: Forwarding from <#{source_id}> on <t:{int(start.timestamp())}:f>"
    )


class ForwardUpdate(HourlyTask):
    minute = 5
    failure = "Could not plan the forwarding."

    def __init__(self, bot: dBot) -> None:
        super().__init__(bot)
        self.queue: dict[str, asyncio.Task[None]] = {}

    async def cog_unload(self) -> None:
        await super().cog_unload()
        for task in self.queue.values():
            task.cancel()
        await asyncio.gather(*self.queue.values(), return_exceptions=True)
        self.queue.clear()

    async def run_game(self, data: State) -> None:
        self.plan(data.game)

    def plan(self, game: Game) -> bool:
        """Start waiting for a game's update; True if a wait was started."""
        if game.forward is None or game.key in self.queue:
            return False
        data = self.bot.games.get(game.key)
        if data.manifest is None:
            return False
        start = None
        if not data.manifest.maintenance_url:
            now = datetime.now(tz=game.timezone)
            start = next_update(data.tables, game.timezone, now)
            if start is None:
                return False
        task = asyncio.create_task(self.forward_update(game, start))
        self.queue[game.key] = task
        task.add_done_callback(lambda done: self._finished(game.key, done))
        return True

    def _finished(self, key: str, task: asyncio.Task[None]) -> None:
        if self.queue.get(key) is task:
            del self.queue[key]
        if not task.cancelled() and (exc := task.exception()) is not None:
            logger.error("%s: Forwarding failed.", key, exc_info=exc)

    async def forward_update(self, game: Game, start: datetime | None) -> None:
        """Wait until the update is out, then move the notices to the servers.

        With a ``start``, the update is announced and awaited until then; without
        one the game is in maintenance and is polled until it is back.
        """
        assert game.forward is not None
        source_id = game.forward.source_channel_id(scheduled=start is not None)
        if start is not None:
            await self._announce(game, source_id, start)
            while datetime.now(tz=game.timezone) < start:
                await asyncio.sleep(POLL_SECONDS)
        else:
            while not await self.bot.games.is_online(game):
                await asyncio.sleep(POLL_SECONDS)
        await self._forward(game, source_id)

    async def _announce(self, game: Game, source_id: int, start: datetime) -> None:
        channel = await find_channel(
            self.bot, NEXT_UPDATE_CHANNEL_ID, discord.TextChannel
        )
        if channel is None:
            return
        content = announcement(game, source_id, start)
        async for message in channel.history(after=start - WINDOW):
            if message.content == content:
                return
        await channel.send(content)

    async def _forward(self, game: Game, source_id: int) -> int:
        """Forward every message of the source channel, then empty it."""
        assert game.forward is not None
        source = await find_channel(self.bot, source_id, discord.TextChannel)
        if source is None:
            return 0
        targets = [
            channel
            for channel_id in game.forward.targets.values()
            if channel_id
            and (
                channel := await find_channel(self.bot, channel_id, discord.TextChannel)
            )
        ]
        if not targets:
            return 0  # nothing was passed on, so nothing is cleared
        count = 0
        async for message in source.history(oldest_first=True):
            count += 1
            for target in targets:
                try:
                    await message.forward(target)
                except discord.HTTPException:
                    logger.warning(
                        "%s: Could not forward a message to %d.", game.key, target.id
                    )
        await source.purge()
        logger.info("%s: Forwarded %d message(s).", game.key, count)
        return count


async def setup(bot: dBot) -> None:
    await bot.add_cog(ForwardUpdate(bot))
