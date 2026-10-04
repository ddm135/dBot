import asyncio
import logging
from collections.abc import Callable
from typing import Literal

from bot import dBot
from lease import Leader

logger = logging.getLogger(__name__)


CLOSE_TIMEOUT = 15.0


async def supervise(
    leader: Leader,
    /,
    make_bot: Callable[[], dBot],
    token: str,
    *,
    cooldown: float,
    stop: asyncio.Event,
) -> None:
    while not stop.is_set():
        logger.info("Acquiring lease...")
        if not await leader.acquire(stop):
            return

        crashed = await _serve_term(leader, make_bot(), token, stop)
        if crashed:
            leader.mark_unhealthy()

        await leader.release()
        if crashed and not stop.is_set():
            logger.info("Waiting %.0fs before contending again...", cooldown)
            try:
                await asyncio.wait_for(stop.wait(), cooldown)
            except TimeoutError:
                pass


async def _serve_term(
    leader: Leader, bot: dBot, token: str, stop: asyncio.Event
) -> bool:
    bot_task = asyncio.create_task(bot.start(token), name="bot")
    hold_task = asyncio.create_task(leader.hold(), name="lease")
    stop_task = asyncio.create_task(stop.wait(), name="stop")
    crashed = False

    try:
        await asyncio.wait(
            {bot_task, hold_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
        )
        if bot_task.done():
            error = None if bot_task.cancelled() else bot_task.exception()
            if error is not None:
                logger.exception("Crashed!", exc_info=error)
                crashed = True
            else:
                logger.info("Stopped.")
        elif hold_task.done():
            try:
                reason = str(hold_task.result())
                exc: Exception | Literal[False] = False
            except Exception as e:
                reason = "Lease error."
                exc = e
            logger.warning("Stepping down: %s", reason, exc_info=exc)
    finally:
        hold_task.cancel()
        stop_task.cancel()
        try:
            async with asyncio.timeout(CLOSE_TIMEOUT):
                await bot.close()
                await asyncio.wait({bot_task})
        except TimeoutError:
            logger.warning("The bot did not stop within %.0fs.", CLOSE_TIMEOUT)
        except Exception:
            logger.exception("Error while stopping the bot.")
        bot_task.cancel()  # no-op if it already finished
        await asyncio.gather(bot_task, hold_task, stop_task, return_exceptions=True)
    return crashed
