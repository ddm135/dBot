import importlib

from statics.consts import LOCK

from . import alice

if LOCK.exists():
    importlib.reload(alice)

from .alice import Alice, setup

del importlib, alice, LOCK

__all__ = ("setup", "Alice")
__author__ = "ddm135 | Aut"
