import importlib

from statics.consts import LOCK

from . import commons, dalcom_sync, types

if LOCK.exists():
    for module in (commons, types, dalcom_sync):
        importlib.reload(module)

from .dalcom_sync import DalcomSync, setup

del importlib, commons, types, dalcom_sync, LOCK

__all__ = ("setup", "DalcomSync")
__author__ = "ddm135 | Aut"
