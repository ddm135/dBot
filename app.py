import asyncio
import logging
import secrets
import signal
import sys

from bot import dBot
from config import Settings
from lease import Leader, create_lease
from supervisor import supervise

logger = logging.getLogger(__name__)


async def run(settings: Settings) -> None:
    stop = asyncio.Event()

    def request_stop(name: str) -> None:
        if not stop.is_set():
            logger.info("Received %s, shutting down...", name)
            stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        if sys.platform != "win32":
            loop.add_signal_handler(sig, request_stop, sig.name)
        else:
            signal.signal(
                sig,
                lambda signum, _: loop.call_soon_threadsafe(
                    request_stop, signal.Signals(signum).name
                ),
            )

    holder = f"{settings.instance_id}-{secrets.token_hex(4)}"
    backend = create_lease(
        settings.valkey,
        key=settings.lease_key,
        holder=holder,
        ttl=settings.lease_ttl,
        preferred_ttl=settings.preferred_ttl,
    )
    await backend.connect(settings.lease_request_timeout)
    logger.info("Lease backend: %s", backend._client.__class__.__name__)

    leader = Leader(
        backend,
        ttl=settings.lease_ttl,
        renew_every=settings.lease_renew_every,
        poll_every=settings.lease_poll_every,
        margin=settings.lease_margin,
        request_timeout=settings.lease_request_timeout,
        preferred=settings.preferred,
        healthy_for=settings.preferred_healthy_for,
    )
    logger.info(
        "Starting instance %s%s...",
        holder,
        " (preferred)" if settings.preferred else "",
    )

    try:
        await supervise(
            leader,
            lambda: dBot(settings),
            settings.discord_token,
            cooldown=settings.restart_cooldown,
            stop=stop,
        )
    finally:
        await leader.release()
        await backend.close()
