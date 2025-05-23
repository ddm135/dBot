import importlib

from . import autocompletes, commons, embeds

for module in (autocompletes, commons, embeds):
    importlib.reload(module)

from .role import setup  # noqa: E402, F401
