import json
import os
from collections import defaultdict
from datetime import datetime
from typing import Any

import discord
from discord.ext import commands
from dotenv import load_dotenv

from statics.consts import EXTENSIONS, PING_DATA, STATUS_CHANNEL

load_dotenv()


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
    role_data_ready = False

    pings: defaultdict[
        int, defaultdict[str, defaultdict[int, defaultdict[str, list[int]]]]
    ] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list[int])))
    )

    # pings = {
    #     360109303199432704: {
    #         "ddm": {
    #             180925261531840512: {
    #                 "users": [1335307588597710868],
    #                 "channels": [401412343629742090],
    #             }
    #         }
    #     },
    #     540849436868214784: {
    #         "ddm": {
    #             180925261531840512: {
    #                 "users": [],
    #                 "channels": [1335315390732963952],
    #             }
    #         }
    #     },
    # }

    async def setup_hook(self) -> None:
        if PING_DATA.exists():
            with open(PING_DATA, "r") as f:
                pings = json.load(f)
            self.pings = defaultdict(
                lambda: defaultdict(
                    lambda: defaultdict(lambda: defaultdict(list[int]))
                ),
                pings,
            )

        else:
            self.pings = defaultdict(
                lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list[int])))
            )
            with open(PING_DATA, "w") as f:
                json.dump(self.pings, f, indent=4)

        for ext in EXTENSIONS:
            await self.load_extension(ext)

        await super().setup_hook()

    async def on_ready(self) -> None:
        await self.get_channel(STATUS_CHANNEL).send(  # type: ignore[union-attr]
            f"Successful start at {datetime.now()}"
        )

    async def on_message(self, message: discord.Message) -> None:
        if message.guild is not None and not message.author.bot:
            for word in self.pings.get(message.guild.id, []):
                if word not in message.content:
                    continue

                for owner in self.pings[message.guild.id][word]:
                    if (
                        message.author.id == owner
                        or message.author.id
                        in self.pings[message.guild.id][word][owner]["users"]
                        or message.channel.id
                        in self.pings[message.guild.id][word][owner]["channels"]
                    ):
                        continue

                    user = await self.fetch_user(owner)
                    if user is None:
                        continue

                    embed = discord.Embed(
                        description=(
                            f"`{message.author.name}` mentioned `{word}` in "
                            f"<#{message.channel.id}> on "
                            f"<t:{int(message.created_at.timestamp())}:f>\n\n"
                            f"{message.content}"
                        ),
                        color=message.author.color,
                    )
                    embed.set_author(
                        name=f"Word Ping in {message.guild.name}",
                        url=message.jump_url,
                        icon_url=message.guild.icon.url if message.guild.icon else None,
                    )
                    embed.set_thumbnail(url=message.author.display_avatar.url)

                    await user.send(embed=embed)

        return await super().on_message(message)

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
