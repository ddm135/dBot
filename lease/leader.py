"""Winning, holding and giving up the lease.

A standby polls; a leader renews and steps down a margin before its lease would
run out, so it has stopped before another instance can take over. The
preferred instance (the main one) takes the lease back from a standby once it
has been healthy for a while.
"""

import asyncio
import enum
import logging
import math
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class StepDownReason(enum.StrEnum):
    """Why a leader stopped holding the lease."""

    LOST = "The lease is held by another instance."
    EXPIRED = "The lease could not be renewed in time."
    HANDOVER = "The preferred instance is online."


class LeaseBackend(Protocol):
    """What a leader needs of the store that holds the lease (``BaseLease``)."""

    async def acquire_or_renew(self) -> bool: ...

    async def release(self) -> None: ...

    async def advertise_preferred(self) -> None: ...

    async def preferred_waiting(self) -> bool: ...


class Leader:
    """One instance's claim on the lease.

    ``clock`` and ``sleep`` are injectable so the timing can be tested.
    """

    def __init__(
        self,
        backend: LeaseBackend,
        *,
        ttl: float,
        renew_interval: float,
        poll_interval: float,
        margin: float,
        request_timeout: float,
        preferred: bool = False,
        healthy_for: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
    ) -> None:
        self._backend = backend
        self._ttl = ttl
        self._renew_interval = renew_interval
        self._poll_interval = poll_interval
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
            logger.warning("Lease request failed.", exc_info=True)
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
            logger.warning("Could not check for the preferred instance.", exc_info=True)
            return False

    async def _advertise(self) -> None:
        try:
            await asyncio.wait_for(
                self._backend.advertise_preferred(), timeout=self._request_timeout
            )
        except Exception:
            logger.warning("Could not advertise as preferred.", exc_info=True)
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
        """Wait until this instance holds the lease; False if ``stop`` is set first.

        The preferred instance asks for it, and advertises once it has been healthy
        long enough; the others defer while it is advertising.
        """
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
                logger.debug("Deferring to the preferred instance...")
            elif await self._acquire():
                return True
            await self._wait(self._poll_interval, stop)
        return False

    async def hold(self) -> StepDownReason:
        """Keep renewing the lease; return why it could not be held any longer."""
        while True:
            delay = min(
                self._renew_interval, self._valid_until - self._margin - self._clock()
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
        """Give the lease up at once, so another instance need not wait for it to expire."""
        try:
            await asyncio.wait_for(self._backend.release(), self._request_timeout)
        except Exception:
            logger.warning(
                "Could not release lease. It will expire after %d.",
                self.remaining,
                exc_info=True,
            )
        finally:
            self._valid_until = -math.inf
