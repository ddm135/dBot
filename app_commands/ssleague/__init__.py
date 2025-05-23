import importlib

from statics.consts import LOCK

from . import autocompletes, ssleague

if LOCK.exists():
    for module in (autocompletes, ssleague):
        importlib.reload(module)

from .ssleague import setup  # noqa: F401
