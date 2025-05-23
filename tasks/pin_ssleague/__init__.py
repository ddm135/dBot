import importlib

from statics.consts import LOCK

from . import pin_ssleague

if LOCK.exists():
    importlib.reload(pin_ssleague)

from .pin_ssleague import setup  # noqa: F401
