import importlib

from statics.consts import LOCK

from . import info_sync

if LOCK.exists():
    importlib.reload(info_sync)

from .info_sync import setup  # noqa: F401
