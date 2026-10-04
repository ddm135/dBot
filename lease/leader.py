import asyncio
import enum
import logging
import math
import time
from collections.abc import Awaitable, Callable
from typing import Any

from .base import BaseLease

logger = logging.getLogger(__name__)


class StepDownReason(enum.StrEnum):
    LOST = "The lease is held by another instance."
    EXPIRED = "The lease could not be renewed in time."
    HANDOVER = "The preferred instance is online."


class Leader:
    def __init__(
        self,
        backend: BaseLease,
        *,
        ttl: float,
        renew_every: float,
        poll_every: float,
        margin: float,
        request_timeout: float,
        preferred: bool = False,
        healthy_for: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
    ) -> None:
        self._backend = backend
        self._ttl = ttl
        self._renew_every = renew_every
        self._poll_every = poll_every
        self._margin = margin
        self._request_timeout = request_timeout
        self._preferred = preferred
        self._healthy_for = healthy_for
        self._clock = clock
        self._sleep = sleep
        self._valid_until = -math.inf
        self._healthy_since = clock()

    @property
    def remaining(self) -> float:
        return max(0.0, self._valid_until - self._clock())

    def mark_unhealthy(self) -> None:
        self._healthy_since = self._clock()

    async def _acquire(self) -> bool | None:
        started = self._clock()
        try:
            held = await asyncio.wait_for(
                self._backend.acquire_or_renew(), timeout=self._request_timeout
            )
        except Exception:
            logger.exception("Lease request failed.")
            return None

        if held:
            self._valid_until = started + self._ttl
        return held

    async def _preferred_waiting(self) -> bool:
        try:
            return await asyncio.wait_for(
                self._backend.preferred_waiting(), timeout=self._request_timeout
            )
        except Exception:
            logger.exception("Could not check for the preferred instance.")
            return False

    async def _advertise(self) -> None:
        try:
            await asyncio.wait_for(
                self._backend.advertise_preferred(), timeout=self._request_timeout
            )
        except Exception:
            logger.exception("Could not advertise as preferred.")
            self.mark_unhealthy()

    async def _wait(self, delay: float, stop: asyncio.Event | None) -> None:
        if stop is None:
            await self._sleep(delay)
            return
        sleeper = asyncio.ensure_future(self._sleep(delay))
        waiter = asyncio.ensure_future(stop.wait())

        try:
            await asyncio.wait({sleeper, waiter}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            sleeper.cancel()
            waiter.cancel()
            await asyncio.gather(sleeper, waiter, return_exceptions=True)

    async def acquire(self, stop: asyncio.Event | None = None) -> bool:
        while stop is None or not stop.is_set():
            if self._preferred:
                result = await self._acquire()
                if result:
                    return True
                elif result is None:
                    self.mark_unhealthy()
                elif self._clock() - self._healthy_since >= self._healthy_for:
                    await self._advertise()
            elif await self._preferred_waiting():
                pass
            elif await self._acquire():
                return True
            await self._wait(self._poll_every, stop)
        return False

    async def hold(self) -> StepDownReason:
        while True:
            delay = min(
                self._renew_every, self._valid_until - self._margin - self._clock()
            )
            if delay > 0:
                await self._sleep(delay)
            if self._clock() >= self._valid_until - self._margin:
                return StepDownReason.EXPIRED
            result = await self._acquire()
            if result is False:
                return StepDownReason.LOST
            if result and not self._preferred and await self._preferred_waiting():
                return StepDownReason.HANDOVER

    async def release(self) -> None:
        try:
            await asyncio.wait_for(self._backend.release(), self._request_timeout)
        except Exception:
            logger.exception(
                "Could not release lease. It will expire after %d.", self.remaining
            )
        finally:
            self._valid_until = -math.inf
