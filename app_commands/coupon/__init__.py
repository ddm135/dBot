import importlib

from statics.consts import LOCK

from . import commons, coupon

if LOCK.exists():
    for module in (commons, coupon):
        importlib.reload(module)

from .coupon import setup

del importlib, commons, coupon, LOCK

__all__ = ("setup",)
__author__ = "ddm135 | Aut"
