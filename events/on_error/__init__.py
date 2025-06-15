import importlib

from statics.consts import LOCK

from . import on_error

if LOCK.exists():
    importlib.reload(on_error)

from .on_error import setup

del importlib, on_error, LOCK

__all__ = ("setup",)
__author__ = "ddm135 | Aut"
