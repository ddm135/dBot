import importlib

from statics.consts import LOCK

from . import border_sync, commons

if LOCK.exists():
    for module in (commons, border_sync):
        importlib.reload(module)

from .border_sync import BorderSync, setup

del importlib, commons, border_sync, LOCK

__all__ = ("setup", "BorderSync")
__author__ = "ddm135 | Aut"
