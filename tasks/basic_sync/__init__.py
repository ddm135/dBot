import importlib

from statics.consts import LOCK

from . import basic_sync

if LOCK.exists():
    importlib.reload(basic_sync)

from .basic_sync import setup

del importlib, basic_sync, LOCK

__all__ = ("setup",)
__author__ = "ddm135 | Aut"
