"""Tells when the event loop is blocked, and by what.

A loop that is held by heavy work cannot renew the lease, answer an interaction
within Discord's three seconds, or send a heartbeat. A thread outside the loop
asks it for a beat every half second; when one is late it logs where the loop's
thread currently is, which is the code holding it.

If that thread is idle (waiting in ``select``) the loop is not the one at fault:
either another thread holds the interpreter lock, or the host is not giving the
process CPU time. So the report also shows what the other threads are doing, how
much CPU the process used while stalled, and how much the host throttled it.
"""

import asyncio
import logging
import sys
import threading
import time
import traceback
from pathlib import Path

import psutil

logger = logging.getLogger(__name__)

CGROUP_CPU_STAT = Path("/sys/fs/cgroup/cpu.stat")
CGROUP_CPU_MAX = Path("/sys/fs/cgroup/cpu.max")
IDLE_FUNCTIONS = {"select", "poll", "_run_once"}  # where a waiting loop sits
# Where a parked thread sits (an idle worker, the console reader): not worth showing.
PARKED_FUNCTIONS = {"get", "wait", "_read", "acquire"}


def cgroup_cpu_limit() -> float | None:
    """How many cores' worth of CPU the container may use (None: no limit, or unknown)."""
    try:
        quota, period = CGROUP_CPU_MAX.read_text().split()
        return None if quota == "max" else int(quota) / int(period)
    except OSError, ValueError:
        return None


def cgroup_cpu_period_ms() -> float | None:
    """How long the host's CPU accounting period is, in ms (None if unknown).

    A container that spends its quota in a period is frozen, every thread of it,
    until the next period starts, so this is the longest a single freeze can be.
    """
    try:
        return int(CGROUP_CPU_MAX.read_text().split()[1]) / 1000
    except OSError, ValueError, IndexError:
        return None


def cgroup_throttling() -> tuple[int, int] | None:
    """How often and for how long (ms) the host has held this container's CPU back.

    Cumulative; None where the container's cgroup cannot be read.
    """
    try:
        values = dict(line.split() for line in CGROUP_CPU_STAT.read_text().splitlines())
        return int(values["nr_throttled"]), int(values["throttled_usec"]) // 1000
    except OSError, KeyError, ValueError:
        return None


def thread_cpu() -> dict[int, float]:
    """CPU seconds used so far by each thread of the process, by native id."""
    try:
        return {t.id: t.user_time + t.system_time for t in psutil.Process().threads()}
    except psutil.Error, OSError:
        return {}


class LoopWatchdog:
    """Watches the event loop from its own thread.

    The loop is asked to beat every ``interval`` seconds. A beat later than
    ``threshold`` is a stall, and is logged with where the loop was and what the
    process, the other threads and the host were doing meanwhile.
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        *,
        threshold: float = 1.5,
        interval: float = 0.5,
    ) -> None:
        self._loop = loop
        self._threshold = threshold
        self._interval = interval
        self._beat = time.monotonic()
        self._cpu_at_beat = time.process_time()
        self._throttle_seen = cgroup_throttling()
        self._threads_before = thread_cpu()  # taken while the loop was answering
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
        self._cpu_at_beat = time.process_time()

    def _where(self) -> tuple[str, bool]:
        """The loop thread's stack, and whether it is only waiting."""
        frame = sys._current_frames().get(self._thread_id)
        if frame is None:
            return "(unknown)", False
        return (
            "".join(traceback.format_stack(frame, limit=12)).rstrip(),
            frame.f_code.co_name in IDLE_FUNCTIONS,
        )

    def _others(self) -> str:
        names = {t.ident: t.name for t in threading.enumerate()}
        parts = []
        for ident, frame in sys._current_frames().items():
            if ident in (self._thread_id, threading.get_ident()):
                continue
            if frame.f_code.co_name in PARKED_FUNCTIONS:
                continue
            stack = "".join(traceback.format_stack(frame, limit=6)).rstrip()
            parts.append(f"[{names.get(ident, ident)}]\n{stack}")
        return "\n".join(parts) or "(none)"

    def _busiest(self) -> str:
        """Which threads used the CPU since the loop last answered."""
        names = {t.native_id: t.name for t in threading.enumerate()}
        used = {
            ident: seconds - self._threads_before.get(ident, 0.0)
            for ident, seconds in thread_cpu().items()
        }
        top = sorted(used.items(), key=lambda item: item[1], reverse=True)[:4]
        shown = [
            f"{names.get(ident, ident)} {seconds:.1f}s"
            for ident, seconds in top
            if seconds >= 0.05
        ]
        return "CPU by thread: " + (", ".join(shown) or "none above 0.05s") + "."

    def _host(self, late: float) -> str:
        used = time.process_time() - self._cpu_at_beat
        text = f"The process used {used:.1f}s of CPU in those {late:.1f}s"
        if (limit := cgroup_cpu_limit()) is not None:
            period = cgroup_cpu_period_ms()
            text += f" (the host allows {limit * 100:.0f}% of one core"
            text += f", counted per {period:.0f} ms)" if period else ")"
        now = cgroup_throttling()
        if now is not None and self._throttle_seen is not None:
            times, ms = now[0] - self._throttle_seen[0], now[1] - self._throttle_seen[1]
            text += (
                f"; the host throttled it {times} times ({ms} ms) since the last report"
            )
        self._throttle_seen = now or self._throttle_seen
        return text + "."

    def _watch(self) -> None:
        reported = False
        while not self._stopped.wait(self._interval):
            late = time.monotonic() - self._beat
            if late >= self._threshold and not reported:
                reported = True
                where, idle = self._where()
                message = "The event loop has been blocked for %.1fs. It is in:\n%s\n%s"
                # The loop's own code may not be what held it: it can sit at a call
                # that lets go of the interpreter lock and wait to get it back
                # from a thread running C code. So the others are always shown.
                if idle:
                    message += "\nThe loop itself was only waiting."
                message += "\n%s\nOther threads that are working:\n%s"
                logger.warning(
                    message,
                    late,
                    where,
                    self._host(late),
                    self._busiest(),
                    self._others(),
                )
            elif late < self._threshold and reported:
                reported = False
                logger.info("The event loop is responding again.")
            if late < self._interval * 1.5:  # still answering: the baseline
                self._threads_before = thread_cpu()
            try:
                self._loop.call_soon_threadsafe(self._tick)
            except RuntimeError:  # the loop is closed
                return
