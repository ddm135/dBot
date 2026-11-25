"""Reads a game's Unity string tables (album titles and the like) from its bundles."""

import logging
from typing import TYPE_CHECKING

from games.service import State
from games.strings import load_strings

from .hourly import HourlyTask

if TYPE_CHECKING:
    from bot import dBot

logger = logging.getLogger(__name__)


class StringsSync(HourlyTask):
    minute = 15

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
