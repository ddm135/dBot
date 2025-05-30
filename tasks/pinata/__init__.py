import importlib

from statics.consts import LOCK

from . import pinata

if LOCK.exists():
    importlib.reload(pinata)

from .pinata import setup

del importlib, pinata, LOCK

__all__ = ("setup",)
__author__ = "ddm135 | Aut"
