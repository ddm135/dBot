"""Builds every game's index and bonus calendar right after its data changes.

Every instance does this, not only the preferred one: each answers commands from
its own copy. The builds run in threads, so the event loop (and with it the
lease and Discord's three-second window) is never held by them.
"""

import asyncio
import logging
from typing import TYPE_CHECKING

from tuning import freeze_heap

from .hourly import HourlyTask

if TYPE_CHECKING:
    from bot import dBot
    from games.service import State

logger = logging.getLogger(__name__)


class WarmIndexes(HourlyTask):
    # After the catalogs (:05), tables (:10) and strings (:15).
    minute = 20
    failure = "Preparing the index failed."

    async def run_game(self, data: State) -> None:
        await self.bot.indexes.warm(data.game.key)

    async def finish(self) -> None:
        # Everything is built and settled: keep the collector from walking it
        # again for every bundle read from now on.
        await asyncio.to_thread(freeze_heap)


async def setup(bot: dBot) -> None:
    await bot.add_cog(WarmIndexes(bot))
