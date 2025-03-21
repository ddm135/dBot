import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from discord.ext import commands, tasks

from static.dHelpers import clear_sheet_data, get_sheet_data, update_sheet_data

if TYPE_CHECKING:
    from dBot import dBot


class InfoSync(commands.Cog):
    LOCKED = Path("data/role/locked")
    LOGGER = logging.getLogger(__name__)
    SHEET = "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s"

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        if self.LOCKED.exists():
            self._upload_role_data()
        else:
            self._download_role_data()
        self.bot.role_data_ready = True
        self.role_sync.start()
        await super().cog_load()

    async def cog_unload(self) -> None:
        self.bot.role_data_ready = False
        self.role_sync.cancel()
        self._upload_role_data()
        await super().cog_unload()

    @tasks.loop(hours=1)
    async def role_sync(self) -> None:
        self._upload_role_data()

    def _download_role_data(self) -> None:
        if self.LOCKED.exists():
            return

        self.LOGGER.info("Downloading role data...")
        data_path = Path("data/role")
        data_files = data_path.glob("*.txt")
        for data_file in data_files:
            data_file.unlink()
        role_data = get_sheet_data(self.SHEET, "Roles!A:C")
        for row in role_data:
            file_path = Path(f"data/role/{row[0]}.txt")
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(row[1])

    def _upload_role_data(self) -> None:
        if not self.LOCKED.exists():
            return

        self.LOGGER.info("Uploading role data...")
        data_path = Path("data/role")
        data_files = data_path.glob("*.txt")
        role_data = []
        for data_file in data_files:
            user_id = data_file.stem
            roles = data_file.read_text()
            role_data.append([user_id, roles, "."])
        clear_sheet_data(self.SHEET, "Roles")
        update_sheet_data(self.SHEET, "Roles!A1", False, role_data)
        self.LOCKED.unlink()

    @role_sync.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()
        self.bot.role_data_ready = False
        await asyncio.sleep(5)

    @role_sync.after_loop
    async def after_loop(self) -> None:
        if not self.role_sync.is_being_cancelled():
            await asyncio.sleep(5)
            self.bot.role_data_ready = True
