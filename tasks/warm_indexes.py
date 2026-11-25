"""Builds every game's index and bonus calendar right after its data changes.

Every instance does this, not only the preferred one: each answers commands from
its own copy. The builds run in threads, so the event loop (and with it the
lease and Discord's three-second window) is never held by them.
"""

import logging
from typing import TYPE_CHECKING

from .hourly import HourlyTask

if TYPE_CHECKING:
    from bot import dBot

logger = logging.getLogger(__name__)


class WarmIndexes(HourlyTask):
    # After the catalogs (:05), tables (:10) and strings (:15).
    minute = 20

    async def run_all(self) -> bool:
        for data in self.bot.games:
            try:
                await self.bot.indexes.warm(data.game.key)
            except Exception:
                logger.exception("%s: Preparing the index failed.", data.game.key)
        return True


async def setup(bot: dBot) -> None:
    await bot.add_cog(WarmIndexes(bot))
