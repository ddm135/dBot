import importlib

from statics.consts import LOCK

from . import commons, superstar, types

if LOCK.exists():
    for module in (commons, types, superstar):
        importlib.reload(module)

from .superstar import setup

del importlib, commons, types, superstar, LOCK

__all__ = ("setup",)
__author__ = "ddm135 | Aut"
