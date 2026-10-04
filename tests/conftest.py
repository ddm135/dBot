import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
from dataclasses import replace
from types import MappingProxyType

import pytest_asyncio

from games import registry

# The real games show names in the language their owner prefers (Korean first
# for most). The tests read English names, so every game is set to that here;
# a test of the language order says so itself.
registry.GAMES = MappingProxyType(
    {
        key: replace(game, languages=("enUS", "koKR"))
        for key, game in registry.GAMES.items()
    }
)

from config import PostgresSettings

TEST_DSN = os.environ.get("DBOT_TEST_PG")  # "host:port:user:database"


@pytest_asyncio.fixture
async def database():
    """A fresh, migrated database. Skipped unless DBOT_TEST_PG is set."""
    import pytest

    from db import Database, create_pool, migrate

    if not TEST_DSN:
        pytest.skip("DBOT_TEST_PG is not set")
    host, port, user, name = TEST_DSN.split(":")
    settings = PostgresSettings(
        host, int(port), user, None, use_tls=False, database=name
    )
    pool = await create_pool(settings)
    async with pool.acquire() as conn:
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
    await migrate(pool)
    db = Database(pool)
    yield db
    await pool.close()
