import importlib

from statics.consts import LOCK

from . import commons, pinata, types

if LOCK.exists():
    for module in (commons, types, pinata):
        importlib.reload(module)

from .pinata import setup

del importlib, commons, types, pinata, LOCK

__all__ = ("setup",)
__author__ = "ddm135 | Aut"
