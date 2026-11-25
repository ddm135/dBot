"""Measures every song's charts (note counts and lengths) from the game's bundles.

Only the preferred instance does this; it saves the result in the database, which
every instance reads.
"""

import logging
from typing import TYPE_CHECKING

from games.apks import needs_apk
from games.service import State
from games.song_sync import SyncResult, sync_seq_stats

from .hourly import HourlyTask

if TYPE_CHECKING:
    from bot import dBot

logger = logging.getLogger(__name__)


class SongStatsSync(HourlyTask):
    minute = 15

    def __init__(self, bot: dBot) -> None:
        super().__init__(bot)
        self._known_bad: set[str] = set()

    async def run_all(self) -> bool:
        """Measure every game. Skipped (False) if a run is already going, or if this
        is not the preferred instance."""
        if not self.bot.settings.preferred or self._running.locked():
            return False
        async with self._running:
            for data in self.bot.games:
                try:
                    await self.sync_game(data)
                except Exception:
                    logger.exception("%s: Measuring songs failed.", data.game.key)
        return True

    async def sync_game(self, data: State) -> SyncResult | None:
        game = data.game
        if "MusicData" not in data.tables:
            return None
        database = self.bot.db.song_stats
        stored = await database.load(game.key)

        async def save() -> None:
            await database.save(game.key, stored)

        catalog = data.catalog.catalog if data.catalog else None
        if catalog is not None and needs_apk(data.tables, catalog):
            await self.bot.apks.prefetch(
                game.key
            )  # built-in charts and images live there
        result = await sync_seq_stats(
            game.key,
            data.tables,
            catalog,
            self.bot.bundles,
            stored,
            save,
            known_bad=self._known_bad,
            seq_pattern=game.catalog_patterns.seq if game.catalog_patterns else None,
        )
        await save()  # the carried-over stats too, even if nothing was measured
        if result.updated or result.failed or result.built_in or result.downloaded:
            logger.info(
                "%s: Charts measured %d, unchanged %d, built in %d, missing %d, "
                "failed %d; bundles kept %d.",
                game.key,
                result.updated,
                result.unchanged,
                result.built_in,
                result.missing,
                result.failed,
                result.downloaded,
            )
        return result


async def setup(bot: dBot) -> None:
    await bot.add_cog(SongStatsSync(bot))
