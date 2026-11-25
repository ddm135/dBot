"""Keeps every game's album-art and emblem bundles on disk.

Only the preferred instance does this, ahead of time. Other instances download
a bundle when a picture from it is first asked for. Nothing is unpacked: the
pictures are still read from the kept bundles on demand.
"""

import logging
from typing import TYPE_CHECKING

from games.images import PrefetchResult

from .hourly import HourlyTask

if TYPE_CHECKING:
    from bot import dBot

logger = logging.getLogger(__name__)


class ImageBundles(HourlyTask):
    minute = 30

    async def run_all(self) -> bool:
        """Skipped (False) if a run is already going, or this is not the
        preferred instance."""
        if not self.bot.settings.preferred or self._running.locked():
            return False
        async with self._running:
            images = self.bot.images
            for data in self.bot.games:
                key = data.game.key
                for what, prefetch in (
                    ("Album", images.prefetch_albums),
                    ("Emblem", images.prefetch_emblems),
                ):
                    try:
                        result = await prefetch(key)
                    except Exception:
                        logger.exception("%s: Keeping %s bundles failed.", key, what)
                        continue
                    self._report(key, what, result)
        return True

    @staticmethod
    def _report(key: str, what: str, result: PrefetchResult) -> None:
        if result.downloaded or result.failed:
            logger.info(
                "%s: %s bundles downloaded %d, kept %d, failed %d.",
                key,
                what,
                result.downloaded,
                result.kept,
                result.failed,
            )


async def setup(bot: dBot) -> None:
    await bot.add_cog(ImageBundles(bot))
