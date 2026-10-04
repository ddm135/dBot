"""Reads a game's Unity string tables (album titles and the like) from its bundles."""

import asyncio
import logging
from datetime import time
from typing import TYPE_CHECKING

from discord.ext import commands, tasks

from games.service import State
from games.strings import load_strings

if TYPE_CHECKING:
    from bot import dBot

logger = logging.getLogger(__name__)


class StringsSync(commands.Cog):
    def __init__(self, bot: dBot) -> None:
        self.bot = bot
        self._running = asyncio.Lock()
        self._startup: asyncio.Task[None] | None = None

    async def cog_load(self) -> None:
        self.sync.start()
        self._startup = asyncio.create_task(self._first_run())

    async def cog_unload(self) -> None:
        self.sync.cancel()
        if self._startup is not None:
            self._startup.cancel()
            await asyncio.gather(self._startup, return_exceptions=True)

    async def _first_run(self) -> None:
        await self.bot.games.wait_until_ready()
        await self.run_all()

    # After the catalogs (:00) and tables (:10) have been refreshed.
    @tasks.loop(time=[time(hour=hour, minute=15) for hour in range(24)])
    async def sync(self) -> None:
        await self.bot.games.wait_until_ready()
        await self.run_all()

    async def run_all(self) -> bool:
        if self._running.locked():
            return False
        async with self._running:
            for data in self.bot.games:
                try:
                    await self.sync_game(data)
                except Exception:
                    logger.exception("%s: Reading strings failed.", data.game.key)
        return True

    async def sync_game(self, data: State) -> bool:
        """Read the game's strings. True if they changed."""
        config = data.game.strings
        if config is None or data.catalog is None:
            return False
        strings = await load_strings(
            data.game.key, data.catalog.catalog, self.bot.bundles, config
        )
        if not strings or strings == data.strings:
            return False  # keep the old ones; an unchanged set keeps the index cached
        data.strings = strings
        logger.info("%s: %d strings read.", data.game.key, len(strings))
        return True


async def setup(bot: dBot) -> None:
    await bot.add_cog(StringsSync(bot))
