import os
from collections import defaultdict
from datetime import datetime

import discord
from discord.ext import commands
from dotenv import load_dotenv

from static.dConsts import EXTENSIONS, STATUS_CHANNEL

load_dotenv()


class dBot(commands.Bot):
    info_by_name: defaultdict[
        str, defaultdict[str, defaultdict[str, tuple[str, ...]]]
    ] = defaultdict(lambda: defaultdict(lambda: defaultdict(tuple[str, ...])))
    info_by_id: defaultdict[str, defaultdict[str, tuple[str, ...]]] = defaultdict(
        lambda: defaultdict(tuple[str, ...])
    )
    info_color: defaultdict[str, list[dict]] = defaultdict(list[dict])
    info_data_ready = False
    role_data_ready = False

    async def setup_hook(self) -> None:
        for ext in EXTENSIONS:
            await self.load_extension(ext)
        await super().setup_hook()

    async def on_ready(self) -> None:
        await self.get_channel(STATUS_CHANNEL).send(  # type: ignore[union-attr]
            f"Successful start at {datetime.now()}"
        )

    async def close(self) -> None:
        if self is not None:
            await self.get_channel(STATUS_CHANNEL).send(  # type: ignore[union-attr]
                "Shutting down..."
            )
        await super().close()


intents = discord.Intents.default()
intents.message_content = True
bot = dBot(
    command_prefix="db!",
    help_command=None,
    intents=intents,
    status=discord.Status.dnd,
    activity=discord.CustomActivity("Waiting for clock..."),
)


bot.run(
    os.getenv("DISCORD_TOKEN"),  # type: ignore[arg-type]
    root_logger=True,
)
