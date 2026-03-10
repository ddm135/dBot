import importlib

from statics.consts import LOCK

from . import spreadsheet_sync

if LOCK.exists():
    importlib.reload(spreadsheet_sync)

from .spreadsheet_sync import SpreadsheetSync, setup

del importlib, spreadsheet_sync, LOCK

__all__ = ("setup", "SpreadsheetSync")
__author__ = "ddm135 | Aut"
