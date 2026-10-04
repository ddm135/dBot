from config import ValkeySettings

from .base import BaseLease
from .glide import GlideLease
from .leader import Leader
from .supervisor import supervise
from .valkey import ValkeyLease


def create_lease_backend(
    settings: ValkeySettings,
    /,
    key: str,
    holder: str,
    ttl: float,
    *,
    preferred_key: str | None = None,
    preferred_ttl: float = 15.0,
) -> BaseLease:
    import sys

    backend = GlideLease if sys.platform != "win32" else ValkeyLease
    return backend(
        settings,
        key=key,
        holder=holder,
        ttl=ttl,
        preferred_key=preferred_key,
        preferred_ttl=preferred_ttl,
    )


__all__ = ["BaseLease", "Leader", "create_lease_backend", "supervise"]
