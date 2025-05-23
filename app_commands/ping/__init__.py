import importlib

from . import autocompletes, embeds

for module in (autocompletes, embeds):
    importlib.reload(module)

from .ping import setup  # noqa: E402, F401
