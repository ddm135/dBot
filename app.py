import asyncio
import logging
import secrets
import signal
import sys
from concurrent.futures import ThreadPoolExecutor

from bot import dBot
from config import Settings
from lease import BaseLease, Leader, create_lease_backend, supervise
from lease.watchdog import LoopWatchdog

logger = logging.getLogger(__name__)

CONNECT_BACKOFF_MAX = 30.0
WORKER_THREADS = 4  # for file, parsing and bundle work (see run)


def _install_signal_handlers(stop: asyncio.Event) -> None:
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


async def _connect_lease_backend(
    backend: BaseLease, request_timeout: float, stop: asyncio.Event
) -> bool:
    delay = 1.0
    while not stop.is_set():
        try:
            await backend.connect(request_timeout)
        except Exception:
            logger.warning(
                "Could not connect to the lease backend, retrying in %.0fs...",
                delay,
                exc_info=True,
            )

            try:
                await backend.close()
            except Exception:
                logger.debug("Error while closing the lease backend.", exc_info=True)

            try:
                await asyncio.wait_for(stop.wait(), delay)
            except TimeoutError:
                delay = min(delay * 2, CONNECT_BACKOFF_MAX)
            else:
                return False
        else:
            return True
    return False


async def run(settings: Settings) -> None:
    stop = asyncio.Event()
    _install_signal_handlers(stop)

    holder = f"{settings.instance_id}-{secrets.token_hex(4)}"
    backend = create_lease_backend(
        settings.valkey,
        key=settings.lease_key,
        holder=holder,
        ttl=settings.lease_ttl,
        preferred_ttl=settings.preferred_ttl,
    )
    if not await _connect_lease_backend(backend, settings.lease_request_timeout, stop):
        return
    logger.info("Lease backend: %s", backend.name)

    leader = Leader(
        backend,
        ttl=settings.lease_ttl,
        renew_interval=settings.lease_renew_interval,
        poll_interval=settings.lease_poll_interval,
        margin=settings.lease_margin,
        request_timeout=settings.lease_request_timeout,
        preferred=settings.preferred,
        healthy_for=settings.preferred_healthy_for,
    )
    logger.info(
        "Instance ID: %s%s",
        holder,
        " (preferred)" if settings.preferred else "",
    )

    # The default thread pool is sized for the host's CPUs, not for the share of
    # them this container is given: eight busy threads spend a CPU quota in a
    # fraction of its period, and the host then freezes all of them, the event
    # loop too, until the next period.
    asyncio.get_running_loop().set_default_executor(
        ThreadPoolExecutor(max_workers=WORKER_THREADS, thread_name_prefix="work")
    )
    watchdog = LoopWatchdog(asyncio.get_running_loop())
    watchdog.start()
    try:
        await supervise(
            leader,
            lambda: dBot(settings),
            settings.discord_token,
            cooldown=settings.restart_cooldown,
            stop=stop,
            close_timeout=settings.close_timeout,
        )
    finally:
        watchdog.stop()
        await leader.release()
        await backend.close()
