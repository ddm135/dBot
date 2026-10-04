import importlib

from statics.consts import LOCK

from . import commons, forward_update

if LOCK.exists():
    for module in (commons, forward_update):
        importlib.reload(module)

from .forward_update import ForwardUpdate, setup

del importlib, commons, forward_update, LOCK

__all__ = ("setup", "ForwardUpdate")
__author__ = "ddm135 | Aut"
