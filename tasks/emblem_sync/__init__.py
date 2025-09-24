import importlib

from statics.consts import LOCK

from . import emblem_sync

if LOCK.exists():
    importlib.reload(emblem_sync)

from .emblem_sync import EmblemSync, setup

del importlib, emblem_sync, LOCK

__all__ = ("setup", "EmblemSync")
__author__ = "ddm135 | Aut"
