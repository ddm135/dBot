import importlib

from statics.consts import LOCK

from . import miscellaneous

if LOCK.exists():
    importlib.reload(miscellaneous)

from .miscellaneous import setup

__all__ = ("setup",)
__author__ = "ddm135 | Aut"
