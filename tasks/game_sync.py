"""Brings each game's data up to date every hour: its version, then its tables.

The first full sync is made when the bot starts (``DataService.sync_all``), so
these do not also run at start-up.
"""

import logging
from collections.abc import Awaitable
from typing import TYPE_CHECKING, ClassVar

from .hourly import HourlyTask

if TYPE_CHECKING:
    from bot import dBot

logger = logging.getLogger(__name__)


class _GameSync(HourlyTask):
    """Calls :meth:`sync_all` at ``minute`` past every hour, and logs what failed."""

    at_startup = False
    incomplete: ClassVar[str]  # logged with the names of the games that failed
    crashed: ClassVar[str]

    def sync_all(self) -> Awaitable[list[str]]:
        raise NotImplementedError

    async def run_all(self) -> bool:
        if self._running.locked():
            return False
        async with self._running:
            try:
                if failed := await self.sync_all():
                    logger.warning(self.incomplete, ", ".join(failed))
            except Exception:
                logger.exception(self.crashed)
        return True


class BasicSync(_GameSync):
    """The hourly sync of every game's version, manifest and catalog (minute 5)."""

    minute = 5
    incomplete = "Basic sync failed for: %s."
    crashed = "The basic sync crashed."

    def sync_all(self) -> Awaitable[list[str]]:
        return self.bot.games.sync_basic()


class DalcomSync(_GameSync):
    """The hourly sync of every game's data tables (minute 10)."""

    minute = 10
    incomplete = "Table sync is incomplete for: %s."
    crashed = "The table sync crashed."

    def sync_all(self) -> Awaitable[list[str]]:
        return self.bot.games.sync_tables()


async def setup(bot: dBot) -> None:
    await bot.add_cog(BasicSync(bot))
    await bot.add_cog(DalcomSync(bot))
