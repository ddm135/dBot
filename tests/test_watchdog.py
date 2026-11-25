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


async def test_the_report_says_how_much_cpu_was_used(caplog):
    watchdog = LoopWatchdog(asyncio.get_running_loop(), threshold=0.2, interval=0.05)
    with caplog.at_level(logging.WARNING):
        watchdog.start()
        await asyncio.sleep(0.15)
        _hold_the_loop()
        await asyncio.sleep(0.2)
        watchdog.stop()
    assert "of CPU in those" in caplog.text


def test_the_host_throttling_is_read_from_the_cgroup(tmp_path, monkeypatch):
    import lease.watchdog as module

    stat = tmp_path / "cpu.stat"
    stat.write_text("usage_usec 5\nnr_throttled 7\nthrottled_usec 3500000\n")
    monkeypatch.setattr(module, "CGROUP_CPU_STAT", stat)
    assert module.cgroup_throttling() == (7, 3500)
    monkeypatch.setattr(module, "CGROUP_CPU_STAT", tmp_path / "missing")
    assert module.cgroup_throttling() is None


def test_the_cpu_quota_is_read_from_the_cgroup(tmp_path, monkeypatch):
    import lease.watchdog as module

    limit = tmp_path / "cpu.max"
    monkeypatch.setattr(module, "CGROUP_CPU_MAX", limit)
    limit.write_text("50000 100000\n")
    assert module.cgroup_cpu_limit() == 0.5
    assert module.cgroup_cpu_period_ms() == 100
    limit.write_text("max 100000\n")
    assert module.cgroup_cpu_limit() is None
    monkeypatch.setattr(module, "CGROUP_CPU_MAX", tmp_path / "missing")
    assert module.cgroup_cpu_limit() is None


async def test_the_report_names_the_thread_that_used_the_cpu(caplog):
    import threading

    def spin() -> None:
        end = time.thread_time() + 0.3
        while time.thread_time() < end:
            pass

    watchdog = LoopWatchdog(asyncio.get_running_loop(), threshold=0.2, interval=0.05)
    with caplog.at_level(logging.WARNING):
        watchdog.start()
        await asyncio.sleep(0.15)
        worker = threading.Thread(target=spin, name="burner")
        worker.start()
        _hold_the_loop()
        worker.join()
        await asyncio.sleep(0.1)
        watchdog.stop()
    assert "CPU by thread:" in caplog.text and "burner" in caplog.text
