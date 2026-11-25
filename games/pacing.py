"""Lets a long job in a worker thread leave the host's CPU quota some room.

The host allows a share of one core, counted per 100 ms; a process that spends
it is frozen until the next period, and if the frozen thread holds the
interpreter lock, the event loop is frozen with it. A job that works in short
slices and rests between them never trips the quota, and the loop keeps
running in the rests.
"""

import time


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
            if self._rest:
                time.sleep(worked * self._rest)
            self._mark = time.thread_time()
