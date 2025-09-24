import importlib

from statics.consts import LOCK

from . import bonus_sync

if LOCK.exists():
    importlib.reload(bonus_sync)

from .bonus_sync import BonusSync, setup

del importlib, bonus_sync, LOCK

__all__ = ("setup", "BonusSync")
__author__ = "ddm135 | Aut"
