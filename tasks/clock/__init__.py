import importlib

from statics.consts import LOCK

from . import clock

if LOCK.exists():
    importlib.reload(clock)

from .clock import setup

__all__ = ("setup",)
__author__ = "ddm135 | Aut"
