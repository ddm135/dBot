import asyncio
import logging
import time
from collections.abc import Callable

from discord.ext import commands

from .console import listen
from .leader import Leader

logger = logging.getLogger(__name__)


async def supervise(
    leader: Leader,
    /,
    make_bot: Callable[[], commands.Bot],
    token: str,
    *,
    cooldown: float,
    stop: asyncio.Event,
    close_timeout: float = 15.0,
) -> None:
    while not stop.is_set():
        logger.info("Acquiring lease...")
        if not await leader.acquire(stop):
            return

        crashed = await _serve_term(
            leader, make_bot(), token, stop=stop, close_timeout=close_timeout
        )
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
    leader: Leader,
    /,
    bot: commands.Bot,
    token: str,
    *,
    stop: asyncio.Event,
    close_timeout: float,
) -> bool:
    bot_task = asyncio.create_task(bot.start(token), name="bot")
    hold_task = asyncio.create_task(leader.hold(), name="lease")
    stop_task = asyncio.create_task(stop.wait(), name="stop")
    console_task = asyncio.create_task(listen(bot), name="console")
    crashed = False

    try:
        await asyncio.wait(
            {bot_task, hold_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
        )
        if bot_task.done():
            error = None if bot_task.cancelled() else bot_task.exception()
            if error is not None:
                logger.error("Crashed!", exc_info=error)
                crashed = True
            else:
                logger.info("Stopped.")
        elif hold_task.done():
            try:
                reason = str(hold_task.result())
                logger.warning("Stepping down: %s", reason)
            except Exception:
                reason = "Lease error."
                logger.warning("Stepping down: %s", reason, exc_info=True)
    finally:
        console_task.cancel()
        hold_task.cancel()
        stop_task.cancel()
        started = time.monotonic()
        try:
            async with asyncio.timeout(close_timeout):
                await bot.close()
                await asyncio.wait({bot_task})
            logger.info("The bot stopped in %.1fs.", time.monotonic() - started)
        except TimeoutError:
            logger.warning("The bot did not stop within %.0fs.", close_timeout)
            await _drop_connection(bot)
        except Exception:
            logger.exception("Error while stopping the bot.")
            await _drop_connection(bot)
        bot_task.cancel()
        await asyncio.gather(
            bot_task, hold_task, stop_task, console_task, return_exceptions=True
        )
    return crashed


async def _drop_connection(bot: commands.Bot) -> None:
    """Close the gateway cleanly when the bot could not finish stopping.

    Without a close frame Discord keeps showing the bot (with its last status)
    until the session times out, so this is worth a few seconds.
    """
    ws = getattr(bot, "ws", None)
    if ws is None or not getattr(ws, "open", False):
        return
    try:
        async with asyncio.timeout(5):
            await ws.close(code=1000)
        logger.info("Closed the connection to Discord.")
    except Exception:
        logger.debug("Could not close the connection to Discord.", exc_info=True)
