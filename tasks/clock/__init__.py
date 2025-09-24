import importlib

from statics.consts import LOCK

from . import clock, commons

if LOCK.exists():
    for module in (commons, clock):
        importlib.reload(module)

from .clock import Clock, setup

del importlib, commons, clock, LOCK

__all__ = ("setup", "Clock")
__author__ = "ddm135 | Aut"
