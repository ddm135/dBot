"""The shape shared by the tasks that run every hour (and once at start-up)."""

import asyncio
import logging
from collections.abc import Iterable
from datetime import time
from typing import TYPE_CHECKING, ClassVar

from discord.ext import commands, tasks

if TYPE_CHECKING:
    from bot import dBot
    from games.service import State


class HourlyTask(commands.Cog):
    """Runs :meth:`run_all` at ``minute`` past every hour, and once at start-up.

    The first run does not wait for the hour, so what came due while the bot was
    down is not left until the next one. Every run waits for the games' first data.

    The usual task does the same work for each game, and only has to say what
    that is: it writes :meth:`run_game` (and, to cover the games it is for,
    :meth:`games`; to do something once afterwards, :meth:`finish`) and sets
    ``failure``. A game that raises is logged and the others still run. The lock
    keeps the start-up run and an hourly one from overlapping; a task with a
    different shape writes :meth:`run_all` itself and may use the lock too.
    """

    minute: ClassVar[int] = 0
    at_startup: ClassVar[bool] = True  # False if something else already ran it
    only_preferred: ClassVar[bool] = False  # only the preferred instance does it
    skip_when_running: ClassVar[bool] = True  # False: a run waits for the one before
    failure: ClassVar[str] = "The run failed."  # logged, after the game's key

    def __init__(self, bot: dBot) -> None:
        self.bot = bot
        self._running = asyncio.Lock()
        self._startup: asyncio.Task[None] | None = None
        self._hourly = tasks.loop(
            time=[time(hour=hour, minute=self.minute) for hour in range(24)]
        )(self._tick)

    async def cog_load(self) -> None:
        self._hourly.start()
        if self.at_startup:
            self._startup = asyncio.create_task(self._tick())

    async def cog_unload(self) -> None:
        self._hourly.cancel()
        if self._startup is not None:
            self._startup.cancel()
            await asyncio.gather(self._startup, return_exceptions=True)

    async def _tick(self) -> None:
        await self.bot.games.wait_until_ready()
        await self.run_all()

    def games(self) -> Iterable[State]:
        return self.bot.games

    async def run_game(self, data: State) -> object:
        raise NotImplementedError

    async def finish(self) -> None:
        """Once the games are done, under the lock."""

    async def each_game(self) -> None:
        for data in self.games():
            try:
                await self.run_game(data)
            except Exception:
                logging.getLogger(type(self).__module__).exception(
                    "%s: %s", data.game.key, self.failure
                )

    async def run_all(self) -> bool | None:
        """Skipped (False) if a run is going, or this is not for this instance."""
        if self.only_preferred and not self.bot.settings.preferred:
            return False
        if self.skip_when_running and self._running.locked():
            return False
        async with self._running:
            await self.each_game()
            await self.finish()
        return True
