import importlib

from statics.consts import LOCK

from . import artist_sync

if LOCK.exists():
    importlib.reload(artist_sync)

from .artist_sync import ArtistSync, setup

del importlib, artist_sync, LOCK

__all__ = ("setup", "ArtistSync")
__author__ = "ddm135 | Aut"
