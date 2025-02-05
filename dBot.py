from datetime import datetime, time
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from static.dConsts import DISCORD_TOKEN, STATUS_CHANNEL


class dBot(commands.Bot):
    async def setup_hook(self):
        await self.load_extension("commands.administrative")
        await self.load_extension("commands.memes")
        await self.load_extension("app_commands.bonus")
        await self.load_extension("app_commands.ssLeague")
        await self.load_extension("tasks.clock")
        await self.load_extension("tasks.notify_p9")
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


bot.run(DISCORD_TOKEN)
