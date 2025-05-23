import importlib

from statics.consts import LOCK

from . import data_sync

if LOCK.exists():
    importlib.reload(data_sync)

from .data_sync import setup  # noqa: F401
