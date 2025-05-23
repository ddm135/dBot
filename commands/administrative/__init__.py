import importlib

from statics.consts import LOCK

from . import administrative

if LOCK.exists():
    importlib.reload(administrative)

from .administrative import setup  # noqa: F401
