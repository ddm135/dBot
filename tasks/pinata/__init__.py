import importlib

from statics.consts import LOCK

from . import pinata

if LOCK.exists():
    importlib.reload(pinata)

from .pinata import setup  # noqa: F401
