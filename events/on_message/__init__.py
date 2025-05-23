import importlib

from . import embeds

importlib.reload(embeds)

from .on_message import setup  # noqa: E402, F401
