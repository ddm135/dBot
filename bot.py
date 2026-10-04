import logging

import discord
from discord.ext import commands

from config import Settings

logger = logging.getLogger(__name__)


class dBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            command_prefix=["db!", "DB!", "dB!", "Db!"],
            help_command=None,
            intents=discord.Intents.all(),
            status=discord.Status.idle,
            activity=discord.CustomActivity("Waiting for clock..."),
            member_cache_flags=discord.MemberCacheFlags.all(),
        )
        self.settings = settings

    async def setup_hook(self):
        logger.info("Ready!")

    async def on_command_error(self, _, exception: commands.CommandError, /):
        if isinstance(
            exception,
            (
                commands.NotOwner,
                commands.CommandNotFound,
                commands.MissingRequiredArgument,
            ),
        ):
            return
        raise exception
