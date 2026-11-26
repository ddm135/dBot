"""World-record leaderboards from the game's rank server."""

import asyncio
import logging
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from games.errors import ServerError
from games.http import DEFAULT_RETRY, RetryPolicy, fetch

logger = logging.getLogger(__name__)

CACHE_SECONDS = 60.0
CONCURRENCY = 8


class WorldRecordError(ServerError):
    """The rank server could not be reached or gave something unreadable."""


@dataclass(frozen=True, slots=True)
class Record:
    """One leaderboard entry."""

    rank: int
    nickname: str
    highscore: int


@dataclass(frozen=True, slots=True)
class Leaderboard:
    """The records of an item and when the server last changed them."""

    records: tuple[Record, ...] = ()
    updated: datetime | None = None  # when the server last changed it


def parse_records(data: object) -> tuple[Record, ...]:
    """Records from the server's JSON list; entries that are not records are skipped."""
    if not isinstance(data, list):
        return ()
    records = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        nickname, score = entry.get("nickname"), entry.get("highscore")
        rank = entry.get("rank", 1)  # a leaderboard of one has no rank
        if (
            isinstance(nickname, str)
            and isinstance(score, int)
            and isinstance(rank, int)
        ):
            records.append(Record(rank, nickname, score))
    return tuple(records)


def parse_last_modified(value: str | None, timezone: ZoneInfo) -> datetime | None:
    """The server's ``Last-Modified`` header as a time, or None."""
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(timezone)
    except TypeError, ValueError:
        return None


class WorldRecords:
    """The rank server's boards, kept for a few minutes so repeated commands do not ask
    again.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        ttl: float = CACHE_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        retry: RetryPolicy = DEFAULT_RETRY,
    ) -> None:
        self._client = client
        self._ttl = ttl
        self._clock = clock
        self._retry = retry
        self._cache: dict[str, tuple[float, Leaderboard]] = {}

    async def fetch(
        self,
        base_url: str,
        season: int,
        item_id: int,
        timezone: ZoneInfo,
        *,
        first_only: bool = False,
    ) -> Leaderboard:
        """The top records of an item (a song, or an artist for weekly seasons).

        Tries the full board first, then the one with only the leader.
        Raises :class:`WorldRecordError` if the server cannot be read; an item
        nobody has played gives an empty board.
        """
        root = f"{base_url.rstrip('/')}/{season}/{item_id}/"
        names = (
            ["latest_first.json"]
            if first_only
            else ["latest.json", "latest_first.json"]
        )
        for name in names:
            board = await self._get(root + name, timezone)
            if board is not None:
                return board
        return Leaderboard()

    async def fetch_many(
        self,
        base_url: str,
        season: int,
        item_ids: Iterable[int],
        timezone: ZoneInfo,
        *,
        first_only: bool = False,
    ) -> dict[int, Leaderboard | WorldRecordError]:
        """Several items at once, a few at a time; failures are returned, not raised."""
        gate = asyncio.Semaphore(CONCURRENCY)

        async def one(item: int) -> Leaderboard | WorldRecordError:
            async with gate:
                try:
                    return await self.fetch(
                        base_url, season, item, timezone, first_only=first_only
                    )
                except WorldRecordError as exc:
                    return exc

        ids = list(item_ids)
        results = await asyncio.gather(*(one(i) for i in ids))
        return dict(zip(ids, results, strict=True))

    async def _get(self, url: str, timezone: ZoneInfo) -> Leaderboard | None:
        cached = self._cache.get(url)
        if cached and self._clock() < cached[0]:
            return cached[1]
        response = await fetch(
            self._client,
            url,
            retry=self._retry,
            error=WorldRecordError,
            ok=(200, 403, 404),
        )
        if response.status_code != 200:
            return None  # nothing there (yet)
        try:
            data: Any = response.json()
        except ValueError as exc:
            raise WorldRecordError("The rank server's answer is not JSON.") from exc
        board = Leaderboard(
            parse_records(data),
            parse_last_modified(response.headers.get("Last-Modified"), timezone),
        )
        self._cache[url] = (self._clock() + self._ttl, board)
        return board
