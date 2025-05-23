import importlib

from statics.consts import LOCK

from . import autocompletes, commons, embeds, info, views

if LOCK.exists():
    for module in (autocompletes, commons, embeds, views, info):
        importlib.reload(module)

from .info import setup

__all__ = ("setup",)
__author__ = "ddm135 | Aut"
