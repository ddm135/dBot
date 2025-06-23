import importlib

from statics.consts import LOCK

from . import commons, google_sheets

if LOCK.exists():
    for module in (commons, google_sheets):
        importlib.reload(module)

from .google_sheets import setup

del importlib, commons, google_sheets, LOCK

__all__ = ("setup",)
__author__ = "ddm135 | Aut"
