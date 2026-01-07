import logging
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands
from dotenv import load_dotenv

from statics.consts import EXTENSIONS, LOCK, STATUS_CHANNEL
from statics.types import BasicDetails, LastAppearance, LastAppearanceManual


class dBot(commands.Bot):
    LOGGER = logging.getLogger("dBot")

    basic: dict[str, BasicDetails] = {}

    info_by_name: dict[str, dict[str, dict[str, list[str]]]] = {}
    info_by_id: dict[str, dict[str, list[str]]] = {}
    info_from_file: dict[str, dict[str, dict[str, dict]]] = {}

    bonus: dict[str, dict[str, list[list]]] = {}

    emblem: dict[str, dict[str, str | Path | None]] = {}

    word_pings: defaultdict[str, defaultdict[str, defaultdict[str, dict]]] = (
        defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    )
    roles: defaultdict[str, list[int]] = defaultdict(list[int])
    ssleagues: defaultdict[str, defaultdict[str, LastAppearance]] = defaultdict(
        lambda: defaultdict(
            lambda: LastAppearance(songs=defaultdict(lambda: None), date=None)
        )
    )
    ssleague_manual: dict[str, LastAppearanceManual] = {}

    async def setup_hook(self) -> None:
        for ext in EXTENSIONS:
            await self.load_extension(ext)
        LOCK.touch(exist_ok=True)
        self.LOGGER.info("Ready!")

    async def close(self) -> None:
        try:
            channel = self.get_channel(STATUS_CHANNEL) or await self.fetch_channel(
                STATUS_CHANNEL
            )
            assert isinstance(channel, discord.TextChannel)
            # if datetime.now(tz=ZoneInfo("Etc/GMT+8")).hour in (3, 4, 5):
            #     await channel.send("Restarting...")
            # else:
            #     await channel.send("Shutting down...")
            await channel.send(
                f"Shutdown initiated at {datetime.now(tz=ZoneInfo("Etc/GMT+8"))} GMT+8"
            )
        except Exception:
            pass
        finally:
            await super().close()
            LOCK.unlink(missing_ok=True)


bot = dBot(
    command_prefix=["db!", "DB!", "dB!", "Db!"],
    help_command=None,
    intents=discord.Intents.all(),
    status=discord.Status.idle,
    activity=discord.CustomActivity("Waiting for clock..."),
    member_cache_flags=discord.MemberCacheFlags.all(),
)
bot.owner_id = 180925261531840512

load_dotenv()
bot.run(
    os.getenv("DISCORD_TOKEN"),  # type: ignore[arg-type]
    root_logger=True,
)
