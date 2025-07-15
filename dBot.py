# pylint: disable=invalid-name

import logging
import os
from collections import defaultdict

import discord
from discord.ext import commands
from dotenv import load_dotenv

from statics.consts import EXTENSIONS, LOCK, STATUS_CHANNEL
from statics.types import LastAppearance


class dBot(commands.Bot):
    LOGGER = logging.getLogger("dBot")

    ajs: defaultdict[str, dict] = defaultdict(dict)
    grd: defaultdict[str, list[dict]] = defaultdict(list[dict])
    msd: defaultdict[str, list[dict]] = defaultdict(list[dict])
    url: defaultdict[str, list[dict]] = defaultdict(list[dict])

    info_by_name: defaultdict[str, defaultdict[str, defaultdict[str, list[str]]]] = (
        defaultdict(lambda: defaultdict(lambda: defaultdict(list[str])))
    )
    info_by_id: defaultdict[str, defaultdict[str, list[str]]] = defaultdict(
        lambda: defaultdict(list[str])
    )
    info_ready = False

    bonus: defaultdict[str, defaultdict[str, list[list]]] = defaultdict(
        lambda: defaultdict(list[list])
    )
    bonus_ready = False

    credentials: dict = {}
    pings: defaultdict[str, defaultdict[str, defaultdict[str, dict]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(dict))
    )
    roles: defaultdict[str, list[int]] = defaultdict(list[int])
    ssleague: defaultdict[str, defaultdict[str, LastAppearance]] = defaultdict(
        lambda: defaultdict(
            lambda: LastAppearance(songs=defaultdict(lambda: None), date=None)
        )
    )
    ssleague_manual: dict[str, dict[str, str]] = {}

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
            await channel.send("Shutting down...")
        except Exception:  # pylint: disable=broad-exception-caught
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

load_dotenv()
bot.run(
    os.getenv("DISCORD_TOKEN"),  # type: ignore[arg-type]
    root_logger=True,
)
