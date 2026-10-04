"""Pins the SSL song of the day in the configured channels."""

import asyncio
import logging
from datetime import time
from typing import TYPE_CHECKING

from discord.ext import commands, tasks

from games.errors import ServiceError
from games.models import Game
from games.ssleague import fetch_todays_song
from ssl_pins import ssl_day

if TYPE_CHECKING:
    from bot import dBot

logger = logging.getLogger(__name__)


class PinSSL(commands.Cog):
    def __init__(self, bot: dBot) -> None:
        self.bot = bot
        self._running = asyncio.Lock()
        self._startup: asyncio.Task[None] | None = None

    async def cog_load(self) -> None:
        self.pin_all.start()
        self._startup = asyncio.create_task(self._first_run())

    async def cog_unload(self) -> None:
        self.pin_all.cancel()
        if self._startup is not None:
            self._startup.cancel()
            await asyncio.gather(self._startup, return_exceptions=True)

    async def _first_run(self) -> None:
        """Pin a song missed while the bot was down, without waiting for the hour."""
        await self.bot.games.wait_until_ready()
        await self.run_all()

    @tasks.loop(time=[time(hour=hour) for hour in range(24)])
    async def pin_all(self) -> None:
        await self.bot.games.wait_until_ready()
        await self.run_all()

    async def run_all(self) -> None:
        async with self._running:  # a day's song is never pinned twice at once
            results = await asyncio.gather(
                *(self.pin_game(game) for game in self._games()),
                return_exceptions=True,
            )
        for result in results:
            if isinstance(result, Exception):
                logger.error("SSL pin failed.", exc_info=result)

    def _games(self) -> list[Game]:
        return [data.game for data in self.bot.games if data.game.has_pins]

    async def pin_game(self, game: Game) -> None:
        if await self.bot.db.ssl.pinned_on(game.key, ssl_day(game).date()):
            return
        data = self.bot.games.get(game.key)
        account = await self.bot.accounts.get(game.key)
        if account is None or data.manifest is None:
            return
        try:
            song = await fetch_todays_song(account, data.manifest)
        except ServiceError as exc:
            logger.warning("%s: Could not get the SSL song: %s", game.key, exc)
            return  # tried again at the next hour
        try:
            pinned = await self.bot.ssl.pin(game, song, list(game.pins), "dBot")
        except LookupError:
            logger.warning("%s: SSL song %d is not in the data.", game.key, song)
            return
        logger.info(
            "%s: Pinned SSL song %d in %d server(s).", game.key, song, len(pinned)
        )


async def setup(bot: dBot) -> None:
    await bot.add_cog(PinSSL(bot))
