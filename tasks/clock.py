"""The clock: the bot's status shows the date and time, a different timezone each minute."""

import logging
from datetime import UTC, datetime, time
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import aiohttp
import discord
from discord.ext import commands, tasks

if TYPE_CHECKING:
    from bot import dBot

logger = logging.getLogger(__name__)

TIMEZONES = {
    "KST": ZoneInfo("Asia/Seoul"),
    "JST": ZoneInfo("Asia/Tokyo"),
    "CST": ZoneInfo("Asia/Taipei"),
    "ET": ZoneInfo("America/New_York"),
    "PHT": ZoneInfo("Asia/Manila"),
    "ICT": ZoneInfo("Asia/Bangkok"),
    "UTC": ZoneInfo("UTC"),
}
ZONES = tuple(TIMEZONES.items())


class Clock(commands.Cog):
    """Updates the custom status once a minute, cycling through ``TIMEZONES``.

    On a stop that is not a shutdown it leaves a "Clock is disabled." status instead.
    """

    def __init__(self, bot: dBot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.tick.start()

    async def cog_unload(self) -> None:
        self.tick.cancel()

        if self.bot.shutting_down:
            return

        await self.bot.change_presence(
            status=discord.Status.dnd,
            activity=discord.CustomActivity("Clock is disabled."),
        )

    @tasks.loop(time=[time(h, m) for h in range(24) for m in range(60)])
    async def tick(self) -> None:
        now = datetime.now(UTC)
        name, tz = ZONES[int(now.timestamp() // 60) % len(ZONES)]
        local = now.astimezone(tz)
        label = local.tzname() if len(name) == 2 else name

        try:
            await self.bot.change_presence(
                activity=discord.CustomActivity(
                    f"{local:%B} {local.day}, {local.year}, "
                    f"{local.hour}:{local.minute:02d} {label}"
                )
            )
        except discord.ConnectionClosed, aiohttp.ClientConnectionResetError:
            logger.debug("The gateway is reconnecting; skipped a clock update.")

    @tick.before_loop
    async def before_tick(self) -> None:
        await self.bot.wait_until_ready()
        await self.tick()


async def setup(bot: dBot) -> None:
    await bot.add_cog(Clock(bot))
