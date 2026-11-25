import asyncio
import logging
import time
from datetime import datetime
from typing import Any

import discord
import httpx
from discord.ext import commands

from cogs.status import STATUS_TZ, announce, stop_message
from config import Settings
from db import Database
from extensions import EXTENSIONS
from games.accounts import Accounts
from games.apks import ApkStore
from games.bundles import BundleStore
from games.crypto import Cipher
from games.http import create_client
from games.images import ImageService
from games.index import Indexes
from games.registry import GAMES
from games.service import DataService
from games.song_stats import SongStatsStore
from games.stores import PlayStore
from games.world_records import WorldRecords
from search import Searcher
from ssl_pins import SslPinner

logger = logging.getLogger(__name__)

# The bot has no voice features; discord.py warns about the missing voice
# libraries once, when the first client is made.
discord.VoiceClient.warn_nacl = False
discord.VoiceClient.warn_dave = False

SHUTDOWN_NOTICE_TIMEOUT = 5.0  # seconds to tell Discord we are shutting down

IGNORED_COMMAND_ERRORS = (
    commands.CheckFailure,
    commands.CommandNotFound,
    commands.MissingRequiredArgument,
)


class dBot(commands.Bot):
    web: httpx.AsyncClient
    games: DataService
    db: Database
    indexes: Indexes
    stats: SongStatsStore
    apks: ApkStore
    bundles: BundleStore
    images: ImageService
    world_records: WorldRecords
    search: Searcher
    accounts: Accounts
    ssl: SslPinner

    def __init__(self, settings: Settings) -> None:
        super().__init__(
            command_prefix=["db!", "DB!", "dB!", "Db!"],
            help_command=None,
            intents=discord.Intents(
                guilds=True,
                guild_messages=True,
                message_content=True,
            ),
            status=discord.Status.idle,
            activity=discord.CustomActivity("Waiting for clock..."),
        )
        self.settings = settings
        self.shutting_down = False
        self.web = create_client()
        play = PlayStore()
        self.apks = ApkStore(settings.data_dir, self.web, play)
        self.games = DataService(
            settings.data_dir,
            client=self.web,
            cipher=Cipher(settings.aes_key),
            play=play,
            apks=self.apks,
        )
        self.indexes = Indexes(self.games)
        self.bundles = BundleStore(settings.data_dir, self.web, apks=self.apks)
        self.images = ImageService(self.bundles, self.games, self.indexes)
        self.world_records = WorldRecords(self.web)
        self.ssl = SslPinner(self)
        self._first_sync: asyncio.Task[None] | None = None

    async def setup_hook(self) -> None:
        self.db = await Database.connect(self.settings.postgres)
        self.stats = SongStatsStore(self.db.song_stats)
        self.accounts = Accounts(self.games.server, self.db.credentials)
        self.search = Searcher(self.indexes, self.db.aliases)
        await self.search.load(GAMES)
        for key in GAMES:
            self.indexes.set_names(key, await self.db.display_names.all(key))
        self._first_sync = asyncio.create_task(
            self.games.sync_all(), name="first game data sync"
        )
        for extension in EXTENSIONS:
            await self.load_extension(extension)
        logger.info("Ready!")

    async def on_command_error(
        self,
        context: commands.Context[Any],
        exception: commands.CommandError,
        /,
    ) -> None:
        if isinstance(exception, IGNORED_COMMAND_ERRORS):
            return
        raise exception

    async def close(self) -> None:
        self.shutting_down = True
        started = time.monotonic()
        try:
            if not self.is_closed():
                presence, message = stop_message(datetime.now(tz=STATUS_TZ))
                try:
                    # Short: nothing may hold up closing the connection, or
                    # Discord keeps showing this status long after the bot is gone.
                    async with asyncio.timeout(SHUTDOWN_NOTICE_TIMEOUT):
                        # The status first, then the message, as v0 did: the
                        # pause before disconnecting lets Discord take the status
                        # before the session ends, or it can outlive the bot.
                        await self.change_presence(
                            status=discord.Status.dnd,
                            activity=discord.CustomActivity(presence),
                        )
                        await announce(self, message)
                except Exception:
                    logger.warning("Could not announce the shutdown.", exc_info=True)
        finally:
            logger.info(
                "Closing the connection to Discord (%.1fs).",
                time.monotonic() - started,
            )
            try:
                await super().close()
            finally:
                await self._close_services()

    async def _close_services(self) -> None:
        if self._first_sync is not None and not self._first_sync.done():
            self._first_sync.cancel()
            await asyncio.gather(self._first_sync, return_exceptions=True)
        try:
            await self.games.close()
            await self.web.aclose()
        finally:
            if hasattr(self, "db"):
                await self.db.close()
