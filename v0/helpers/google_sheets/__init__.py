import importlib

from statics.consts import LOCK

from . import commons, google_sheets

if LOCK.exists():
    for module in (commons, google_sheets):
        importlib.reload(module)

from .google_sheets import GoogleSheets, setup

del importlib, commons, google_sheets, LOCK

__all__ = ("setup", "GoogleSheets")
__author__ = "ddm135 | Aut"
