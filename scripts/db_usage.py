"""What is using the database: size, tables, dead rows and connections.

    uv run python -m scripts.db_usage

Read-only. Meant for a small server (an Aiven free plan has about 1 GB of memory
and little disk): it shows which tables are big or full of dead rows (a table
that is rewritten often, like ``song_stats``, can grow far beyond its data until
it is vacuumed) and how many connections are open, each of which costs memory.
"""

import asyncio
import sys
from datetime import datetime
from typing import NamedTuple

from asyncpg_typed import sql
from dotenv import load_dotenv

from config import PostgresSettings
from db.database import create_pool


class _Table(NamedTuple):
    relname: str
    live: int
    dead: int
    size: int  # bytes, with indexes and TOAST
    vacuumed: datetime | None


class _Connection(NamedTuple):
    state: str
    total: int


_DATABASE_SIZE = sql(t"SELECT pg_database_size(current_database())", result=int)

_TABLES = sql(
    t"SELECT relname::text AS relname, n_live_tup AS live, n_dead_tup AS dead, "
    t"pg_total_relation_size(relid) AS size, "
    t"GREATEST(last_autovacuum, last_vacuum) AS vacuumed "
    t"FROM pg_stat_user_tables ORDER BY 4 DESC",
    resultset=_Table,
)

_CONNECTIONS = sql(
    t"SELECT coalesce(state, 'background')::text AS state, count(*) AS total "
    t"FROM pg_stat_activity WHERE datname = current_database() "
    t"GROUP BY 1 ORDER BY 2 DESC",
    resultset=_Connection,
)

_SETTING = sql(t"SELECT current_setting({1})", arg=str, result=str)


def _size(count: int) -> str:
    value = float(count)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{count} B"
        value /= 1024
    raise AssertionError  # unreachable


async def report() -> None:
    """Print the database size, the tables and their dead rows, and the connections."""
    pool = await create_pool(PostgresSettings.from_env(), max_size=1)
    try:
        async with pool.acquire() as conn:
            total = await _DATABASE_SIZE.fetchval(conn)
            print(f"Database size: {_size(total)}")
            for name in ("shared_buffers", "work_mem", "max_connections"):
                print(f"{name}: {await _SETTING.fetchval(conn, name)}")
            print("\nTables (size, live rows, dead rows, last vacuum):")
            for t in await _TABLES.fetch(conn):
                share = t.dead / max(1, t.live + t.dead)
                flag = "  <- many dead rows" if t.dead > 1000 and share > 0.2 else ""
                when = f"{t.vacuumed:%Y-%m-%d %H:%M}" if t.vacuumed else "never"
                print(
                    f"  {t.relname:24} {_size(t.size):>10}  {t.live:>8} live"
                    f"  {t.dead:>8} dead  {when}{flag}"
                )
            print("\nConnections to this database:")
            for c in await _CONNECTIONS.fetch(conn):
                print(f"  {c.state:20} {c.total}")
    finally:
        await pool.close()


def main() -> int:
    load_dotenv()
    asyncio.run(report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
