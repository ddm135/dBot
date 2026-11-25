"""Tells when the event loop is blocked, and by what.

A loop that is held by heavy work cannot renew the lease, answer an interaction
within Discord's three seconds, or send a heartbeat. A thread outside the loop
asks it for a beat every half second; when one is late it logs where the loop's
thread currently is, which is the code holding it.
"""

import asyncio
import logging
import sys
import threading
import time
import traceback

logger = logging.getLogger(__name__)


class LoopWatchdog:
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        *,
        threshold: float = 2,
        interval: float = 0.5,
    ) -> None:
        self._loop = loop
        self._threshold = threshold
        self._interval = interval
        self._beat = time.monotonic()
        self._thread_id = threading.get_ident()  # started from the loop's thread
        self._stopped = threading.Event()
        self._watcher = threading.Thread(
            target=self._watch, name="watchdog", daemon=True
        )

    def start(self) -> None:
        self._beat = time.monotonic()
        self._watcher.start()

    def stop(self) -> None:
        self._stopped.set()

    def _tick(self) -> None:
        self._beat = time.monotonic()

    def _where(self) -> str:
        frame = sys._current_frames().get(self._thread_id)
        if frame is None:
            return "(unknown)"
        return "".join(traceback.format_stack(frame, limit=12)).rstrip()

    def _watch(self) -> None:
        reported = False
        while not self._stopped.wait(self._interval):
            late = time.monotonic() - self._beat
            if late >= self._threshold and not reported:
                reported = True
                logger.warning(
                    "The event loop has been blocked for %.1fs. It is in:\n%s",
                    late,
                    self._where(),
                )
            elif late < self._threshold and reported:
                reported = False
                logger.info("The event loop is responding again.")
            try:
                self._loop.call_soon_threadsafe(self._tick)
            except RuntimeError:  # the loop is closed
                return
