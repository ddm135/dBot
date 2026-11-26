"""Leadership of the bot: one instance at a time is connected to Discord.

A lease (a key in Valkey that expires) says who the leader is. :class:`Leader`
acquires and renews it, and :func:`supervise` runs a bot for as long as it holds.
"""

from config import ValkeySettings
from lease.base import BaseLease
from lease.glide import GlideLease
from lease.leader import Leader
from lease.supervisor import supervise
from lease.valkey import ValkeyLease


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
    """The lease backend for this platform: Valkey GLIDE where it is available, the
    plain ``valkey`` client on Windows.
    """
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
