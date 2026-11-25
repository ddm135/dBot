import asyncio
import logging
import time

from lease.watchdog import LoopWatchdog


def _hold_the_loop() -> None:
    time.sleep(0.5)  # stands in for heavy work that never yields


async def test_a_blocked_loop_is_reported_with_where_it_is(caplog):
    watchdog = LoopWatchdog(asyncio.get_running_loop(), threshold=0.2, interval=0.05)
    with caplog.at_level(logging.INFO):
        watchdog.start()
        await asyncio.sleep(0.15)  # beats are flowing
        _hold_the_loop()
        for _ in range(100):  # the loop answers again
            await asyncio.sleep(0.05)
            if "responding again" in caplog.text:
                break
        watchdog.stop()
    text = caplog.text
    assert "blocked for" in text and "_hold_the_loop" in text
    assert "responding again" in text


async def test_a_busy_but_yielding_loop_is_not_reported(caplog):
    watchdog = LoopWatchdog(asyncio.get_running_loop(), threshold=0.3, interval=0.05)
    with caplog.at_level(logging.WARNING):
        watchdog.start()
        for _ in range(10):
            await asyncio.sleep(0.03)
        watchdog.stop()
    assert "blocked" not in caplog.text
