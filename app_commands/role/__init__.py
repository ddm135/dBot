import importlib

from statics.consts import LOCK

from . import autocompletes, commons, embeds, role

if LOCK.exists():
    for module in (autocompletes, commons, embeds, role):
        importlib.reload(module)

from .role import setup  # noqa: F401
