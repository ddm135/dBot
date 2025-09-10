import asyncio
import binascii
import json
from datetime import time
from typing import TYPE_CHECKING

import aiohttp
import discord
from discord.ext import commands, tasks

from statics.consts import GAMES

if TYPE_CHECKING:
    from dBot import dBot


class ForwardUpdate(commands.Cog):
    queue: dict[str, asyncio.Task] = {}

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await self.queue_update()
        self.queue_update.start()

    async def cog_unload(self) -> None:
        self.queue_update.cancel()
        for task in self.queue.values():
            task.cancel()
        self.queue.clear()

    @tasks.loop(time=[time(hour=h, minute=10) for h in range(24)])
    async def queue_update(self) -> None:
        for game, basic_details in self.bot.basic.items():
            if basic_details["manifest"]["MaintenanceUrl"] and game not in self.queue:
                task = asyncio.create_task(self.forward_update(game))
                self.queue[game] = task

    async def forward_update(self, game: str) -> None:
        game_details = GAMES[game]
        if not (forward_details := game_details.get("forward")):
            self.queue.pop(game, None)
            return
        if not (manifestUrl := game_details.get("manifestUrl")):
            self.queue.pop(game, None)
            return

        ss_cog = self.bot.get_cog("SuperStar")
        # basic_cog = self.bot.get_cog("BasicSync")
        async with aiohttp.ClientSession() as session:
            while True:
                await asyncio.sleep(60)
                async with session.get(
                    manifestUrl.format(version=self.bot.basic[game]["version"])
                ) as r:
                    manifest = await r.json(content_type=None)
                if manifest["MaintenanceUrl"]:
                    continue

                try:
                    ajs = await ss_cog.get_a_json(  # type: ignore[union-attr]
                        self.bot.basic[game]
                    )
                    if ajs["code"] == 1000:
                        break
                except (
                    aiohttp.ConnectionTimeoutError,
                    json.JSONDecodeError,
                    binascii.Error,
                    ValueError,
                ):
                    continue

        target_channels = []
        for channel_id in forward_details["target"].values():
            if not channel_id:
                continue

            general_channel = self.bot.get_channel(
                channel_id
            ) or await self.bot.fetch_channel(channel_id)
            assert isinstance(general_channel, discord.TextChannel)
            target_channels.append(general_channel)

        source_channel = self.bot.get_channel(
            forward_details["source"]
        ) or await self.bot.fetch_channel(forward_details["source"])
        assert isinstance(source_channel, discord.TextChannel)

        async for message in source_channel.history(oldest_first=True):
            for target_channel in target_channels:
                try:
                    await message.forward(target_channel)
                except discord.HTTPException:
                    pass

        await source_channel.purge()
        self.queue.pop(game, None)


async def setup(bot: "dBot") -> None:
    await bot.add_cog(ForwardUpdate(bot))
