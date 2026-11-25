"""Connection pool and schema management."""

import logging
import ssl

import asyncpg
from asyncpg_typed import sql

from config import PostgresSettings

from .migrations import MIGRATIONS

logger = logging.getLogger(__name__)

MIGRATION_LOCK = 0x64426F74  # "dBot": serialises migrations across instances
IDLE_SECONDS = 30.0  # close idle connections quickly: small servers have little memory

_LOCK = sql(t"SELECT pg_advisory_lock({1})", arg=int)
_UNLOCK = sql(t"SELECT pg_advisory_unlock({1})", arg=int)

_CREATE_MIGRATIONS = sql(
    t"CREATE TABLE IF NOT EXISTS schema_migrations ("
    t"version integer PRIMARY KEY, "
    t"applied_at timestamptz NOT NULL DEFAULT now())"
)

_APPLIED = sql(t"SELECT version FROM schema_migrations", result=int)

_RECORD_MIGRATION = sql(
    t"INSERT INTO schema_migrations (version) VALUES ({1})",
    arg=int,
)


def tls_context(settings: PostgresSettings) -> ssl.SSLContext | bool:
    """TLS if it is on. A CA file (``POSTGRES_CA_FILE``) is trusted along with the
    system's, for servers such as Aiven's that use their own CA."""
    if not settings.use_tls:
        return False
    context = ssl.create_default_context()
    if settings.ca_file is not None:
        context.load_verify_locations(cafile=str(settings.ca_file))
    return context


async def create_pool(
    settings: PostgresSettings, *, min_size: int = 1, max_size: int | None = None
) -> asyncpg.Pool:
    # JSON columns are left as text on purpose: asyncpg-typed encodes and
    # decodes them itself, so no jsonb codec is registered here.
    tls = tls_context(settings)
    pool = await asyncpg.create_pool(
        host=settings.host,
        port=settings.port,
        user=settings.username,
        password=settings.password,
        database=settings.database or settings.username,
        ssl=tls,
        min_size=min(min_size, max_size or settings.pool_max),
        max_size=max_size or settings.pool_max,
        max_inactive_connection_lifetime=IDLE_SECONDS,
    )
    if pool is None:  # pragma: no cover - asyncpg only returns None for a bad call
        raise RuntimeError("Could not create the database pool.")
    return pool


async def migrate(pool: asyncpg.Pool) -> list[int]:
    """Apply the migrations that are missing; return their versions."""
    applied_now: list[int] = []
    async with pool.acquire() as conn:
        await _LOCK.execute(conn, MIGRATION_LOCK)
        try:
            await _CREATE_MIGRATIONS.execute(conn)
            done = set(await _APPLIED.fetchcol(conn))
            for version, script in MIGRATIONS:
                if version in done:
                    continue
                async with conn.transaction():
                    # A migration is a script of several statements, which cannot
                    # be prepared, so it runs as plain text.
                    await conn.execute(script)
                    await _RECORD_MIGRATION.execute(conn, version)
                logger.info("Applied database migration %d.", version)
                applied_now.append(version)
        finally:
            await _UNLOCK.execute(conn, MIGRATION_LOCK)
    return applied_now
