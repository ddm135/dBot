import importlib

from statics.consts import LOCK

from . import on_ready

if LOCK.exists():
    importlib.reload(on_ready)

from .on_ready import setup

__all__ = ("setup",)
__author__ = "ddm135 | Aut"
