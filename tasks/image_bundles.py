"""Keeps every game's album-art and emblem bundles on disk.

Only the preferred instance does this, ahead of time. Other instances download
a bundle when a picture from it is first asked for. Nothing is unpacked: the
pictures are still read from the kept bundles on demand.
"""

import logging
from typing import TYPE_CHECKING

from games.media.images import PrefetchResult
from tasks.hourly import HourlyTask

if TYPE_CHECKING:
    from bot import dBot
    from games.service import State

logger = logging.getLogger(__name__)


class ImageBundles(HourlyTask):
    """Downloads each game's album-art and emblem bundles on the preferred instance, so
    they are on disk before anyone asks.
    """

    minute = 30
    only_preferred = True
    failure = "Keeping picture bundles failed."

    async def run_game(self, data: State) -> None:
        """Fetch the game's album bundles and its emblem bundles; one kind failing does not
        stop the other.
        """
        key = data.game.key
        images = self.bot.images
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
