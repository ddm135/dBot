import importlib

from statics.consts import LOCK

from . import bonus_sync

if LOCK.exists():
    importlib.reload(bonus_sync)

from .bonus_sync import setup  # noqa: F401
