import importlib

from statics.consts import LOCK

from . import commons, embeds, superstar, types

if LOCK.exists():
    for module in (commons, embeds, types, superstar):
        importlib.reload(module)

from .superstar import SuperStar, setup

del importlib, commons, embeds, types, superstar, LOCK

__all__ = ("setup", "SuperStar")
__author__ = "ddm135 | Aut"
