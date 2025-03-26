import json
import os
import re
from collections import defaultdict
from datetime import datetime
from functools import partial
from typing import Any

import discord
from discord.ext import commands
from dotenv import load_dotenv

from statics.consts import EXTENSIONS, PING_DATA, ROLE_DATA, STATUS_CHANNEL
from statics.types import PingDetails

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

    pings: defaultdict[str, defaultdict[str, defaultdict[str, PingDetails]]]

    roles: defaultdict[str, list[int]]

    async def setup_hook(self) -> None:
        if PING_DATA.exists():
            with open(PING_DATA, "r") as f:
                self.pings = json.load(f)

            self.pings = defaultdict(
                lambda: defaultdict(
                    lambda: defaultdict(dict),  # type: ignore[arg-type]
                ),
                self.pings,
            )
            for key in self.pings:
                self.pings[key] = defaultdict(  # pyright: ignore[reportArgumentType]
                    lambda: defaultdict(dict),  # type: ignore[arg-type]
                    self.pings[key],
                )
                for subkey in self.pings[key]:
                    self.pings[key][subkey] = (  # pyright: ignore[reportArgumentType]
                        defaultdict(
                            dict,  # type: ignore[arg-type]
                            self.pings[key][subkey],
                        )
                    )
        else:
            self.pings = defaultdict(
                lambda: defaultdict(
                    lambda: defaultdict(dict)  # type: ignore[arg-type]
                ),
            )
            with open(PING_DATA, "w") as f:
                json.dump(self.pings, f, indent=4)

        if ROLE_DATA.exists():
            with open(ROLE_DATA, "r") as f:
                self.roles = json.load(f)

            self.roles = defaultdict(list[int], self.roles)
        else:
            self.roles = defaultdict(list[int])
            with open(ROLE_DATA, "w") as f:
                json.dump(self.roles, f, indent=4)

        for ext in EXTENSIONS:
            await self.load_extension(ext)

        await super().setup_hook()

    async def on_ready(self) -> None:
        await self.get_channel(STATUS_CHANNEL).send(  # type: ignore[union-attr]
            f"Successful start at {datetime.now()}"
        )

    async def on_message(self, message: discord.Message) -> None:
        if message.guild is not None and not message.author.bot:
            guild_id = str(message.guild.id)
            for word in self.pings[guild_id]:
                regexp = rf"(?:\s+|^){re.escape(word)}(?:\s+|$)"
                if not re.search(regexp, message.content):
                    continue

                for owner in self.pings[guild_id][word]:
                    _owner = int(owner)
                    if (
                        message.author.id == _owner
                        or not self.pings[guild_id][word][owner]
                        or message.author.id
                        in self.pings[guild_id][word][owner]["users"]
                        or message.channel.id
                        in self.pings[guild_id][word][owner]["channels"]
                    ):
                        continue

                    user = await self.fetch_user(_owner)
                    if user is None:
                        continue

                    self.pings[guild_id][word][owner]["count"] += 1

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
