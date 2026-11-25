"""Process-level memory settings that must be made before the bot starts."""

import ctypes
import logging
import os
import sys

logger = logging.getLogger(__name__)

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
        return bool(ctypes.CDLL("libc.so.6").mallopt(M_ARENA_MAX, count))
    except OSError, AttributeError:  # not glibc (musl, say)
        logger.debug("Could not limit malloc arenas.", exc_info=True)
        return False
