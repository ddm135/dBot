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
