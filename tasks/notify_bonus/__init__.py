import importlib

from statics.consts import LOCK

from . import embeds, notify_bonus

if LOCK.exists():
    for module in (embeds, notify_bonus):
        importlib.reload(module)

from .notify_bonus import setup

__all__ = ("setup",)
__author__ = "ddm135 | Aut"
