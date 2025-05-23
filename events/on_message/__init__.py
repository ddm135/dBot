import importlib

from statics.consts import LOCK

from . import embeds, on_message

if LOCK.exists():
    for module in (embeds, on_message):
        importlib.reload(module)

from .on_message import setup  # noqa: F401
