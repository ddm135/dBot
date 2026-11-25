"""How the process uses the machine: malloc arenas, the garbage collector and freed
memory, and pacing a long job in a thread."""

import ctypes
import gc
import logging
import os
import sys
import time
from contextlib import suppress

logger = logging.getLogger(__name__)


def _libc() -> ctypes.CDLL:
    return ctypes.CDLL("libc.so.6")


M_ARENA_MAX = -8  # glibc's mallopt parameter number
ARENAS = 2


def limit_arenas(count: int = ARENAS) -> bool:
    """Cap glibc's malloc arenas, as ``MALLOC_ARENA_MAX`` would.

    Each thread that allocates gets an arena of its own, and the file writes
    and bundle reads run in many threads; their arenas grow and are hardly ever
    handed back. A host that starts ``python dBot.py`` directly cannot set the
    environment variable, so this does the same from inside, before any thread
    exists. An existing ``MALLOC_ARENA_MAX`` is left alone. Returns whether the
    limit was set (it can only be on Linux with glibc).
    """
    if "MALLOC_ARENA_MAX" in os.environ or not sys.platform.startswith("linux"):
        return False
    try:
        return bool(_libc().mallopt(M_ARENA_MAX, count))
    except OSError, AttributeError:  # not glibc (musl, say)
        logger.debug("Could not limit malloc arenas.", exc_info=True)
        return False


TRIM_EVERY = 5.0  # seconds between returning freed memory to the OS
_last_trim = 0.0


def freeze_heap() -> None:
    """Take everything alive now (the game tables, the indexes) out of the
    cycle collector's sight.

    A collection walks every object the interpreter tracks, and the tables are
    millions of them: seconds of work, with the interpreter held, once for every
    bundle that is opened. Frozen, they are skipped, so a collection only looks
    at what a bundle just made. Call it when the tables have settled.

    It does not collect first: that walks the whole heap, seconds with the
    interpreter held, every time it runs. Tables are made of dicts and lists
    that nothing refers to in a cycle, so what is replaced is freed by its
    reference count even while frozen; only cyclic garbage is left until
    :func:`release_memory` is called with ``everything``.
    """
    gc.freeze()


def release_memory(*, everything: bool = False) -> None:
    """Hand the memory of a finished bundle back, not at some later collection.

    UnityPy's objects refer to each other in cycles, so a bundle (the file, its
    decompressed blocks) lives until the cycle collector runs, and glibc keeps
    what was freed. Several bundles in a row, in threads, then pile up.

    ``everything`` also unfreezes the heap first (see :func:`freeze_heap`), for
    when a whole bot's worth of data has just been dropped.
    """
    global _last_trim
    if everything:
        gc.unfreeze()
    gc.collect()
    now = time.monotonic()
    if sys.platform.startswith("linux") and (
        everything or now - _last_trim >= TRIM_EVERY
    ):
        _last_trim = now
        with suppress(OSError, AttributeError):
            _libc().malloc_trim(0)


class Pacer:
    """Call it often from a loop; it sleeps when the thread has worked a while.

    ``share`` is the part of the time the job may work (0.5: rest as long as it
    worked), ``slice_seconds`` how long it works before it rests.
    """

    def __init__(self, share: float = 0.5, slice_seconds: float = 0.05) -> None:
        if not 0 < share <= 1:
            raise ValueError("share must be above 0 and at most 1")
        self._rest = 1 / share - 1
        self._slice = slice_seconds
        self._mark = time.thread_time()

    def __call__(self) -> None:
        worked = time.thread_time() - self._mark
        if worked >= self._slice:
            time.sleep(worked * self._rest)
            self._mark = time.thread_time()
