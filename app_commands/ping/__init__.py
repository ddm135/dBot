import importlib

from statics.consts import LOCK

from . import autocompletes, embeds, ping

if LOCK.exists():
    for module in (autocompletes, embeds, ping):
        importlib.reload(module)

from .ping import setup

del importlib, autocompletes, embeds, ping, LOCK

__all__ = ("setup",)
__author__ = "ddm135 | Aut"
