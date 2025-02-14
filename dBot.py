import os
from datetime import datetime, time
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from static.dConsts import EXTENSIONS, STATUS_CHANNEL

# pyright: reportAttributeAccessIssue=false
# pyright: reportOptionalMemberAccess=false


load_dotenv()


class dBot(commands.Bot):
    async def setup_hook(self):
        for ext in EXTENSIONS:
            await self.load_extension(ext)
        await super().setup_hook()

    async def on_ready(self):
        await self.get_channel(STATUS_CHANNEL).send(
            f"Successful start at {datetime.now()}"
        )

    async def close(self):
        await self.get_channel(STATUS_CHANNEL).send("Shutting down...")
        await super().close()


intents = discord.Intents.default()
intents.message_content = True
bot = dBot(command_prefix="db!", intents=intents)


@tasks.loop(
    time=[
        time(
            hour=11,
            minute=59,
            second=59,
            microsecond=999999,
            tzinfo=ZoneInfo("Asia/Seoul"),
        )
    ]
)
async def restart_clock(ctx: commands.Context):
    await bot.reload_extension("tasks.clock")
    await ctx.send("Clock restarted!")


bot.run(os.getenv("DISCORD_TOKEN"))  # type: ignore[arg-type]
