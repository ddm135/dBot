import importlib

from statics.consts import LOCK

from . import commons, data_sync

if LOCK.exists():
    for module in (commons, data_sync):
        importlib.reload(module)

from .data_sync import DataSync, setup

del importlib, commons, data_sync, LOCK

__all__ = ("setup", "DataSync")
__author__ = "ddm135 | Aut"
