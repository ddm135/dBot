import importlib

from statics.consts import LOCK

from . import pinata, types

if LOCK.exists():
    for module in (types, pinata):
        importlib.reload(module)

from .pinata import setup

del importlib, types, pinata, LOCK

__all__ = ("setup",)
__author__ = "ddm135 | Aut"
