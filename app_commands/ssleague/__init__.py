import importlib

from . import autocompletes

importlib.reload(autocompletes)

from .ssleague import setup  # noqa: E402, F401
