import importlib

from . import autocompletes, commons, embeds, views

for module in (autocompletes, commons, embeds, views):
    importlib.reload(module)

from .bonus import setup  # noqa: E402, F401
