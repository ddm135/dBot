import asyncio
import logging

from lease.supervisor import _serve_term


class Ws:
    def __init__(self):
        self.open = True
        self.codes = []

    async def close(self, code):
        self.codes.append(code)
        self.open = False


class HangingBot:
    def __init__(self):
        self.ws = Ws()

    async def start(self, token):
        await asyncio.Event().wait()

    async def close(self):
        await asyncio.Event().wait()  # e.g. a cog that never finishes unloading


class Leader:
    async def hold(self):
        await asyncio.Event().wait()


async def test_a_bot_that_cannot_finish_closing_still_leaves_discord_cleanly(caplog):
    stop = asyncio.Event()
    stop.set()
    bot = HangingBot()
    with caplog.at_level(logging.WARNING):
        crashed = await _serve_term(
            Leader(),  # type: ignore[arg-type]
            bot,  # type: ignore[arg-type]
            "token",
            stop=stop,
            close_timeout=0.05,
        )
    assert not crashed
    assert bot.ws.codes == [1000]  # the gateway got a proper close
    assert "did not stop" in caplog.text


def test_the_memory_reading_is_a_number_of_megabytes():
    from lease.supervisor import _rss

    value, unit = _rss().split()
    assert unit == "MB" and int(value) > 0
