import importlib

from statics.consts import LOCK

from . import autocompletes, bonus, commons, embeds, types, views

if LOCK.exists():
    for module in (autocompletes, commons, embeds, types, views, bonus):
        importlib.reload(module)

from .bonus import setup

del importlib, autocompletes, commons, embeds, types, views, bonus, LOCK

__all__ = ("setup",)
__author__ = "ddm135 | Aut"
