"""Postgres storage: the pool, the schema, and one small class per feature."""

from typing import Self

import asyncpg

from config import PostgresSettings

from .bonus_pings import BonusPings
from .database import create_pool, migrate
from .misc import Aliases, Credentials, DisplayNames, LiveThemes
from .roles import StoredRoles
from .song_stats import SongStatsDb
from .ssl import SslHistory
from .word_pings import WordPings


class Database:
    """Every store of the bot, over one connection pool.

    Made with :meth:`connect`, which also applies the missing migrations and loads
    the word pings into memory.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool
        self.word_pings = WordPings(pool)
        self.roles = StoredRoles(pool)
        self.ssl = SslHistory(pool)
        self.bonus_pings = BonusPings(pool)
        self.live_themes = LiveThemes(pool)
        self.credentials = Credentials(pool)
        self.aliases = Aliases(pool)
        self.display_names = DisplayNames(pool)
        self.song_stats = SongStatsDb(pool)

    @classmethod
    async def connect(cls, settings: PostgresSettings) -> Self:
        """Open the pool, bring the schema up to date, and load the word pings."""
        pool = await create_pool(settings)
        try:
            await migrate(pool)
            database = cls(pool)
            await database.word_pings.load()
        except BaseException:
            await pool.close()
            raise
        return database

    async def close(self) -> None:
        """Close the pool."""
        await self.pool.close()


__all__ = ["Database", "create_pool", "migrate"]
