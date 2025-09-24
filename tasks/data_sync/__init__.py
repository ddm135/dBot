import importlib

from statics.consts import LOCK

from . import data_sync

if LOCK.exists():
    importlib.reload(data_sync)

from .data_sync import setup, DataSync

del importlib, data_sync, LOCK

__all__ = ("setup", "DataSync")
__author__ = "ddm135 | Aut"
