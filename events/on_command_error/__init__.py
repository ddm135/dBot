import importlib

from statics.consts import LOCK

from . import on_command_error

if LOCK.exists():
    importlib.reload(on_command_error)

from .on_command_error import setup  # noqa: F401
