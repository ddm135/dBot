import sys

from config import ValkeySettings

from .base import BaseLease
from .glide import GlideLease
from .valkey import ValkeyLease


def create_lease(settings: ValkeySettings, **kwargs) -> BaseLease:
    if sys.platform != "win32":
        return GlideLease(settings, **kwargs)
    else:
        return ValkeyLease(settings, **kwargs)
