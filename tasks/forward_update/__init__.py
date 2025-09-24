import importlib

from statics.consts import LOCK

from . import forward_update

if LOCK.exists():
    importlib.reload(forward_update)

from .forward_update import ForwardUpdate, setup

del importlib, forward_update, LOCK

__all__ = ("setup", "ForwardUpdate")
__author__ = "ddm135 | Aut"
