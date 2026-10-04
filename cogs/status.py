"""Start and stop messages in the status channel."""

import logging
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands

from channels import find_channel
from discord_ids import STATUS_CHANNEL_ID

if TYPE_CHECKING:
    from bot import dBot

logger = logging.getLogger(__name__)

STATUS_TZ = ZoneInfo("Etc/GMT-8")
RESTART_HOURS = (3, 4)  # the weekly restart happens Monday at 03:00-04:59


def is_weekly_restart(now: datetime) -> bool:
    return now.hour in RESTART_HOURS and now.weekday() == 0


def stop_message(now: datetime) -> tuple[str, str]:
    """``(presence text, status message)`` for shutting down at ``now``."""
    if is_weekly_restart(now):
        return "Weekly restart in progress...", f"Weekly restart at {now}."
    return "Shutting down...", f"Shutting down at {now}."


async def announce(bot: dBot, text: str) -> None:
    channel = await find_channel(bot, STATUS_CHANNEL_ID, discord.abc.Messageable)
    if channel is None:
        return
    try:
        await channel.send(text)
    except discord.HTTPException:
        logger.warning("Could not post to the status channel.", exc_info=True)


class Status(commands.Cog):
    def __init__(self, bot: dBot) -> None:
        self.bot = bot
        self._started = False

    @commands.Cog.listener("on_ready")
    async def on_ready(self) -> None:
        if self._started:  # on_ready also fires after every reconnect
            return
        self._started = True
        await announce(self.bot, f"Successful start at {datetime.now(tz=STATUS_TZ)}.")


async def setup(bot: dBot) -> None:
    await bot.add_cog(Status(bot))
