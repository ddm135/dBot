import os
from collections import defaultdict
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import commands
from dotenv import load_dotenv

from statics.consts import EXTENSIONS, STATUS_CHANNEL

if TYPE_CHECKING:
    from statics.types import PingDetails


class dBot(commands.Bot):
    info_ajs: defaultdict[str, dict[str, Any]] = defaultdict(dict[str, Any])
    info_msd: defaultdict[str, list[dict[str, Any]]] = defaultdict(list[dict[str, Any]])
    info_url: defaultdict[str, list[dict[str, Any]]] = defaultdict(list[dict[str, Any]])
    info_by_name: defaultdict[str, defaultdict[str, defaultdict[str, list[str]]]] = (
        defaultdict(lambda: defaultdict(lambda: defaultdict(list[str])))
    )
    info_by_id: defaultdict[str, defaultdict[str, list[str]]] = defaultdict(
        lambda: defaultdict(list[str])
    )
    info_data_ready = False

    bonus_data: defaultdict[str, defaultdict[str, list[list[Any]]]] = defaultdict(
        lambda: defaultdict(list[list[Any]])
    )
    bonus_data_ready = False

    pings: defaultdict[str, defaultdict[str, defaultdict[str, "PingDetails"]]] = (
        defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(dict),  # type: ignore[arg-type]
            )
        )
    )
    roles: defaultdict[str, list[int]] = defaultdict(list[int])

    async def setup_hook(self) -> None:
        for ext in EXTENSIONS:
            await self.load_extension(ext)

    async def close(self) -> None:
        try:
            await self.get_channel(STATUS_CHANNEL).send(  # type: ignore[union-attr]
                "Shutting down..."
            )
        except AttributeError:
            pass
        finally:
            await super().close()


intents = discord.Intents.default()
intents.message_content = True
bot = dBot(
    command_prefix=["db!", "DB!", "dB!", "Db!"],
    help_command=None,
    intents=intents,
    status=discord.Status.idle,
    activity=discord.CustomActivity("Waiting for clock..."),
)

load_dotenv()
bot.run(
    os.getenv("DISCORD_TOKEN"),  # type: ignore[arg-type]
    root_logger=True,
)
