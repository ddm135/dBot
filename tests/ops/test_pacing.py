import time

import pytest

from ops.tuning import Pacer


def _spin(seconds: float) -> None:
    end = time.thread_time() + seconds
    while time.thread_time() < end:
        pass


def test_a_pacer_rests_as_long_as_the_thread_worked():
    pace = Pacer(share=0.5, slice_seconds=0.02)
    start = time.monotonic()
    _spin(0.05)
    pace()
    assert time.monotonic() - start >= 0.09  # ~0.05 worked + ~0.05 rest


def test_a_pacer_does_not_rest_during_a_short_slice():
    pace = Pacer(share=0.5, slice_seconds=1.0)
    start = time.monotonic()
    _spin(0.01)
    pace()
    assert time.monotonic() - start < 0.1


def test_a_full_share_never_rests():
    pace = Pacer(share=1.0, slice_seconds=0.001)
    start = time.monotonic()
    _spin(0.02)
    pace()
    assert time.monotonic() - start < 0.05


def test_the_share_must_be_a_fraction():
    with pytest.raises(ValueError):
        Pacer(share=0)
