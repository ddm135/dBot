import importlib

from statics.consts import LOCK

from . import commons, google_drive

if LOCK.exists():
    for module in (commons, google_drive):
        importlib.reload(module)

from .google_drive import setup

del importlib, commons, google_drive, LOCK

__all__ = ("setup",)
__author__ = "ddm135 | Aut"
