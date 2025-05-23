import importlib

from statics.consts import LOCK

from . import data_sync

if LOCK.exists():
    importlib.reload(data_sync)

from .data_sync import setup

__all__ = ("setup",)
__author__ = "ddm135 | Aut"
