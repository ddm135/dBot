import importlib

from statics.consts import LOCK

from . import embeds, on_message

if LOCK.exists():
    for module in (embeds, on_message):
        importlib.reload(module)

from .on_message import setup

del importlib, embeds, on_message, LOCK

__all__ = ("setup",)
__author__ = "ddm135 | Aut"
