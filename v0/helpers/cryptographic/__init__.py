import importlib

from statics.consts import LOCK

from . import commons, cryptographic

if LOCK.exists():
    for module in (commons, cryptographic):
        importlib.reload(module)

from .cryptographic import Cryptographic, setup

del importlib, commons, cryptographic, LOCK

__all__ = ("setup", "Cryptographic")
__author__ = "ddm135 | Aut"
