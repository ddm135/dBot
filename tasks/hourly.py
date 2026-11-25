"""The shape shared by the tasks that run every hour (and once at start-up)."""

import asyncio
from datetime import time
from typing import TYPE_CHECKING, ClassVar

from discord.ext import commands, tasks

if TYPE_CHECKING:
    from bot import dBot


class HourlyTask(commands.Cog):
    """Runs :meth:`run_all` at ``minute`` past every hour, and once at start-up.

    The first run does not wait for the hour, so what came due while the bot was
    down is not left until the next one. Every run waits for the games' first data.
    A subclass sets ``minute`` and writes :meth:`run_all`; the lock is its own to
    use so that the start-up run and an hourly one never overlap.
    """

    minute: ClassVar[int] = 0

    def __init__(self, bot: dBot) -> None:
        self.bot = bot
        self._running = asyncio.Lock()
        self._startup: asyncio.Task[None] | None = None
        self._hourly = tasks.loop(
            time=[time(hour=hour, minute=self.minute) for hour in range(24)]
        )(self._tick)

    async def cog_load(self) -> None:
        self._hourly.start()
        self._startup = asyncio.create_task(self._tick_once())

    async def cog_unload(self) -> None:
        self._hourly.cancel()
        if self._startup is not None:
            self._startup.cancel()
            await asyncio.gather(self._startup, return_exceptions=True)

    async def _tick_once(self) -> None:
        await self._tick()

    async def _tick(self) -> None:
        await self.bot.games.wait_until_ready()
        await self.run_all()

    async def run_all(self) -> bool | None:
        raise NotImplementedError
