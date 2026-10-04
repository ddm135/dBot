"""SuperStar roles a user has stored in their inventory."""

from collections.abc import Iterable

import asyncpg
from asyncpg_typed import sql

_GET = sql(
    "SELECT role_id FROM stored_roles WHERE user_id = $1",
    arg=int,
    result=int,
)

_REMOVE = sql(
    "DELETE FROM stored_roles WHERE user_id = $1 AND role_id = ANY($2::bigint[])",
    args=tuple[int, list[int]],
)

# Also used by the v0 import.
INSERT_IGNORING = sql(
    "INSERT INTO stored_roles (user_id, role_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
    args=tuple[int, int],
)


class StoredRoles:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get(self, user_id: int) -> set[int]:
        async with self._pool.acquire() as conn:
            return set(await _GET.fetchcol(conn, user_id))

    async def add(self, user_id: int, role_ids: Iterable[int]) -> None:
        await self.change(user_id, add=role_ids)

    async def remove(self, user_id: int, role_ids: Iterable[int]) -> None:
        await self.change(user_id, remove=role_ids)

    async def change(
        self,
        user_id: int,
        *,
        add: Iterable[int] = (),
        remove: Iterable[int] = (),
    ) -> None:
        """Store and take out roles in one transaction."""
        add, remove = list(add), list(remove)
        async with self._pool.acquire() as conn, conn.transaction():
            if remove:
                await _REMOVE.execute(conn, user_id, remove)
            if add:
                await INSERT_IGNORING.executemany(
                    conn, [(user_id, role) for role in add]
                )
