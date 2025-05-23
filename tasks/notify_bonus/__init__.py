import importlib

from . import embeds

importlib.reload(embeds)

from .notify_bonus import setup  # noqa: E402, F401
