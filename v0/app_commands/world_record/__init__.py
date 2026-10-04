import importlib

from statics.consts import LOCK

from . import autocompletes, commons, embeds, views, world_record

if LOCK.exists():
    for module in (autocompletes, commons, embeds, views, world_record):
        importlib.reload(module)

from .world_record import WorldRecord, setup

del importlib, autocompletes, commons, embeds, views, world_record, LOCK

__all__ = ("setup", "WorldRecord")
__author__ = "ddm135 | Aut"
