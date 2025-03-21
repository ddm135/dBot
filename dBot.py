import os
from collections import defaultdict
from datetime import datetime, time

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from static.dConsts import EXTENSIONS, STATUS_CHANNEL, TIMEZONES

# pyright: reportAttributeAccessIssue=false
# pyright: reportOptionalMemberAccess=false


load_dotenv()


class dBot(commands.Bot):
    info_by_name: defaultdict[str, defaultdict[str, list[list[str]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    info_by_id: defaultdict[str, defaultdict[str, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    info_data_ready: bool = False
    role_data_ready: bool = False

    async def setup_hook(self):
        self.remove_command("help")
        for ext in EXTENSIONS:
            await self.load_extension(ext)
        await super().setup_hook()

    async def on_ready(self):
        await self.get_channel(STATUS_CHANNEL).send(
            f"Successful start at {datetime.now()}"
        )

    async def on_message(self, message: discord.Message) -> None:
        await super().on_message(message)

    async def close(self):
        await self.get_channel(STATUS_CHANNEL).send("Shutting down...")
        await super().close()


intents = discord.Intents.default()
intents.message_content = True
bot = dBot(
    command_prefix="db!",
    intents=intents,
    status=discord.Status.dnd,
    activity=discord.CustomActivity("Starting..."),
)


@tasks.loop(
    time=[
        time(
            hour=11,
            minute=59,
            second=59,
            microsecond=999999,
            tzinfo=TIMEZONES["KST"],
        )
    ]
)
async def restart_clock(ctx: commands.Context):
    await bot.reload_extension("tasks.clock")
    await ctx.send("Clock restarted!")


bot.run(
    os.getenv("DISCORD_TOKEN"),  # type: ignore[arg-type]
    root_logger=True,
)
