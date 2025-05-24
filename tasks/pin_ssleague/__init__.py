import importlib

from statics.consts import LOCK

from . import pin_ssleague

if LOCK.exists():
    importlib.reload(pin_ssleague)

from .pin_ssleague import setup

del importlib, pin_ssleague, LOCK

__all__ = ("setup",)
__author__ = "ddm135 | Aut"
