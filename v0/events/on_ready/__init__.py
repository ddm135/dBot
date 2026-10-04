import importlib

from statics.consts import LOCK

from . import on_ready

if LOCK.exists():
    importlib.reload(on_ready)

from .on_ready import OnReady, setup

del importlib, on_ready, LOCK

__all__ = ("setup", "OnReady")
__author__ = "ddm135 | Aut"
