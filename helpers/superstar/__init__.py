import importlib

from statics.consts import LOCK

from . import superstar

if LOCK.exists():
    importlib.reload(superstar)

from .superstar import setup

del importlib, superstar, LOCK

__all__ = ("setup",)
__author__ = "ddm135 | Aut"
