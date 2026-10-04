import logging
from datetime import time
from typing import TYPE_CHECKING

from discord.ext import commands, tasks

if TYPE_CHECKING:
    from bot import dBot

logger = logging.getLogger(__name__)


class DalcomSync(commands.Cog):
    def __init__(self, bot: dBot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.sync.start()

    async def cog_unload(self) -> None:
        self.sync.cancel()

    @tasks.loop(time=[time(hour=hour, minute=10) for hour in range(24)])
    async def sync(self) -> None:
        try:
            if failed := await self.bot.games.sync_tables():
                logger.warning("Table sync is incomplete for: %s.", ", ".join(failed))
        except Exception:
            logger.exception("The table sync crashed.")


async def setup(bot: dBot) -> None:
    await bot.add_cog(DalcomSync(bot))
