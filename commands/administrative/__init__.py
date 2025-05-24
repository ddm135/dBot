import importlib

from statics.consts import LOCK

from . import administrative

if LOCK.exists():
    importlib.reload(administrative)

from .administrative import setup

del importlib, administrative, LOCK

__all__ = ("setup",)
__author__ = "ddm135 | Aut"
