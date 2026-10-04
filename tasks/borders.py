"""Announces new borders: uploads each to Google Drive and posts its link.

Only the preferred instance does this (and downloads the border bundles)."""

import asyncio
import logging
from datetime import time
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import commands, tasks

from channels import find_channel
from discord_ids import BORDER_CHANNEL_ID
from games.borders import border_files
from games.borders import old_name as _old_name
from games.bundles import BuiltInBundle, BundleError
from games.drive import BorderFolder, Drive, StoredFile
from games.service import State
from ui.text import escape

if TYPE_CHECKING:
    from bot import dBot

logger = logging.getLogger(__name__)


class Borders(commands.Cog):
    def __init__(self, bot: dBot, drive: BorderFolder | None = None) -> None:
        self.bot = bot
        self._drive = drive
        self._running = asyncio.Lock()
        self._startup: asyncio.Task[None] | None = None

    def _folder(self) -> BorderFolder | None:
        if self._drive is None:
            google = self.bot.settings.google
            if not google.credentials_file.is_file():
                logger.warning(
                    "No Google credentials at %s: borders are not announced.",
                    google.credentials_file,
                )
                return None
            self._drive = Drive.from_service_account(
                google.border_folder_id, google.credentials_file
            )
        return self._drive

    async def cog_load(self) -> None:
        self.sync.start()
        self._startup = asyncio.create_task(self._first_run())

    async def cog_unload(self) -> None:
        self.sync.cancel()
        if self._startup is not None:
            self._startup.cancel()
            await asyncio.gather(self._startup, return_exceptions=True)

    async def _first_run(self) -> None:
        await self.bot.games.wait_until_ready()
        await self.run_all()

    # After the catalogs (:00), tables (:10) and song stats (:15).
    @tasks.loop(time=[time(hour=hour, minute=30) for hour in range(24)])
    async def sync(self) -> None:
        await self.bot.games.wait_until_ready()
        await self.run_all()

    async def run_all(self) -> bool:
        if not self.bot.settings.preferred or self._running.locked():
            return False  # only the preferred instance downloads and uploads
        async with self._running:
            for data in self.bot.games:
                try:
                    await self.announce(data)
                except Exception:
                    logger.exception("%s: Announcing borders failed.", data.game.key)
        return True

    async def announce(self, data: State) -> int:
        """Upload and announce the borders the game's folder does not have yet."""
        game = data.game
        if data.catalog is None:
            return 0
        catalog = data.catalog.catalog
        wanted = border_files(game, data.tables, catalog, data.strings)
        if not wanted:
            return 0
        sources = {name: _source(catalog, key) for name, key in wanted.items()}
        # The bundles are kept like the others, whatever Drive has.
        await self._keep_bundles(game.key, catalog, wanted.values())
        folder = self._folder()
        if folder is None:
            return 0
        folder_id = await folder.game_folder(game.name)
        have = await folder.files(folder_id)
        await _adopt_numbered(folder, have, wanted)
        # New ones, and ones the game has republished under the same name. A file
        # from before sources were recorded is left alone: it cannot be compared.
        todo = {
            name: key
            for name, key in wanted.items()
            if name not in have
            or (have[name].source is not None and have[name].source != sources[name])
        }
        if not todo:
            return 0
        channel = await find_channel(self.bot, BORDER_CHANNEL_ID, discord.TextChannel)
        if channel is None:
            return 0
        logger.info("%s: Uploading %d borders.", game.key, len(todo))
        announced = 0
        for name, key in todo.items():
            picture = await self.bot.images.from_catalog(game.key, key)
            if picture is None or picture.data is None:
                continue
            image = picture.data
            note = ""
            if name in have:
                old = _old_name(name, have)
                await folder.rename(have[name].id, old)
                note = " (updated)"
            link = await folder.upload(folder_id, name, image, sources[name])
            await channel.send(f"{game.name}: {escape(name)}{note}\n<{link}>")
            announced += 1
        return announced

    async def _keep_bundles(self, game_key: str, catalog: Any, keys: Any) -> None:
        """Download the bundles the borders are in (they are not unpacked)."""
        urls = {
            url
            for key in keys
            for url in catalog.bundle_urls(key)
            if url and url.startswith(("http://", "https://"))
        }
        for url in sorted(urls):
            try:
                await self.bot.bundles.fetch(game_key, url)
            except (BundleError, BuiltInBundle) as error:
                logger.warning("%s: Border bundle %s: %s", game_key, url, error)


async def _adopt_numbered(
    folder: BorderFolder, have: dict[str, StoredFile], wanted: dict[str, str]
) -> None:
    """Rename files kept as "<number>.png" to their "<number> - <name>.png".

    Borders used to be kept under their number alone; renaming them keeps them
    from being uploaded and announced a second time.
    """
    for name in wanted:
        number, dash, rest = name.partition(" - ")
        if not dash or name in have:
            continue
        old = f"{number}{PurePosixPath(rest).suffix}"
        if old in have:
            await folder.rename(have[old].id, name)
            have[name] = have.pop(old)


def _source(catalog: Any, key: str) -> str:
    """Where a border came from: its catalog key and the id the catalog gives it."""
    ids = [i for i in catalog.internal_ids(key) if i]
    return f"{key}#{ids[0] if ids else ''}"


async def setup(bot: dBot) -> None:
    await bot.add_cog(Borders(bot))
