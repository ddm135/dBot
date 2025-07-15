import importlib

from statics.consts import LOCK

from . import dalcom_sync

if LOCK.exists():
    importlib.reload(dalcom_sync)

from .dalcom_sync import setup

del importlib, dalcom_sync, LOCK

__all__ = ("setup",)
__author__ = "ddm135 | Aut"
