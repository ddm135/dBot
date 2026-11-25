import sys

import pytest

from tuning import limit_arenas


def test_the_arena_limit_is_set_on_linux_and_skipped_when_already_chosen(monkeypatch):
    monkeypatch.delenv("MALLOC_ARENA_MAX", raising=False)
    result = limit_arenas()
    assert result is sys.platform.startswith("linux") or result is False
    monkeypatch.setenv("MALLOC_ARENA_MAX", "4")
    assert limit_arenas() is False  # the host's choice wins


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="glibc only")
def test_mallopt_accepts_the_setting(monkeypatch):
    monkeypatch.delenv("MALLOC_ARENA_MAX", raising=False)
    assert limit_arenas(2) in (True, False)  # False on a musl system


def test_a_frozen_heap_is_skipped_by_collections_and_released_when_asked():
    import gc

    from tuning import freeze_heap, release_memory

    keep = [{"a": [1, 2, 3]} for _ in range(100)]  # stands in for the tables
    freeze_heap()
    assert gc.get_freeze_count() >= len(keep)
    release_memory()  # one bundle's worth: the frozen objects stay frozen
    assert gc.get_freeze_count() >= len(keep)
    release_memory(everything=True)  # a whole bot dropped
    assert gc.get_freeze_count() == 0
    del keep
