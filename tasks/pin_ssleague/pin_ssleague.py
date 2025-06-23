# mypy: disable-error-code="union-attr"
# pyright: reportAttributeAccessIssue=false, reportOptionalMemberAccess=false

import asyncio
import logging
from datetime import datetime, time
from typing import TYPE_CHECKING

import aiohttp
import discord
import discord.backoff
from discord.ext import commands, tasks

from statics.consts import GAMES, RESET_OFFSET
from statics.helpers import (
    pin_new_ssl,
    unpin_old_ssl,
)
from statics.types import SSLeagueEmbed

if TYPE_CHECKING:
    from dBot import dBot


class PinSSLeague(commands.Cog):
    LOGGER = logging.getLogger(__name__)

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.pin_ssls.start()

    async def cog_unload(self) -> None:
        self.pin_ssls.cancel()

    @tasks.loop(time=[time(hour=h) for h in range(24)])
    async def pin_ssls(self) -> None:
        cog = self.bot.get_cog("DataSync")
        cog.save_last_appearance()

        pin_tasks = [
            self.pin_ssl(game, self.bot.credentials[game])
            for game, game_details in GAMES.items()
            if game_details["pinChannelIds"] and game in self.bot.credentials
        ]
        await asyncio.gather(*pin_tasks, return_exceptions=True)

        cog.save_credential_data()
        cog.save_ssleague_data()

    async def pin_ssl(self, game: str, credentials: dict) -> None:
        game_details = GAMES[game]
        timezone = game_details["timezone"]
        current_time = datetime.now(tz=timezone) - RESET_OFFSET
        if current_time.hour:
            return
        api_url = game_details["api"]
        backoff = discord.backoff.ExponentialBackoff()
        cog = self.bot.get_cog("SuperStar")

        while True:
            try:
                credentials["version"] = await cog.get_active_version(
                    game_details["manifest"], credentials
                )
                match credentials["provider"]:
                    case 0 | 1 if not credentials["isSNS"]:
                        oid, key = await cog.login_classic(api_url, credentials)
                    case 0 if credentials["isSNS"]:
                        oid, key = await cog.login_google(
                            api_url, credentials, game_details["target_audience"]
                        )
                    case 3 if credentials["isSNS"]:
                        oid, key = await cog.login_dalcom_id(
                            api_url, credentials, game_details["authorization"]
                        )
                    case _:
                        return
                ssleague = await cog.get_ssleague(api_url, oid, key)
            except aiohttp.ClientError as e:
                self.LOGGER.exception(str(e))
                await asyncio.sleep(backoff.delay())
            else:
                break

        curday = ssleague["result"]["curday"]
        music_list = ssleague["result"]["musicList"]
        music = next(music for music in music_list if music["day"] == curday)
        song_id = music["music"]
        ssl_song = self.bot.info_by_id[game][str(song_id)]

        info_columns = game_details["infoColumns"]
        artist_name_index = info_columns.index("artist_name")
        song_name_index = info_columns.index("song_name")
        duration_index = info_columns.index("duration")
        skills_index = (
            info_columns.index("skills") if "skills" in info_columns else None
        )

        artist_name = ssl_song[artist_name_index]
        song_name = ssl_song[song_name_index]
        duration = ssl_song[duration_index]
        skills = ssl_song[skills_index] if skills_index is not None else None

        msd_data = self.bot.info_msd[game]
        for song in msd_data:
            if song["code"] == song_id:
                color = int(song["albumBgColor"][:-2], 16)
                image_url = song["album"]
                break
        else:
            color = game_details["color"]
            image_url = None

        if game_details["legacyUrlScheme"] and image_url:
            url_data = self.bot.info_url[game]
            for url in url_data:
                if url["code"] == image_url:
                    image_url = url["url"]
                    break

        artist_last_str = self.bot.ssleague[game][artist_name]["date"]
        if artist_last_str:
            artist_last = datetime.strptime(artist_last_str, game_details["dateFormat"])
            artist_last = artist_last.replace(
                tzinfo=timezone, hour=2, minute=0, second=0, microsecond=0
            )
        else:
            artist_last = None

        song_last_str = self.bot.ssleague[game][artist_name]["songs"][str(song_id)]
        if song_last_str:
            song_last = datetime.strptime(song_last_str, game_details["dateFormat"])
            song_last = song_last.replace(
                tzinfo=timezone, hour=2, minute=0, second=0, microsecond=0
            )
        else:
            song_last = None

        embed = SSLeagueEmbed(
            artist_name,
            song_name,
            duration,
            image_url,
            color,
            skills,
            current_time,
            self.bot.user.name,
            artist_last,
            song_last,
        )

        pin_channels = game_details["pinChannelIds"]
        pin_roles = game_details["pinRoles"]
        for guild_id, channel_id in pin_channels.items():
            if not channel_id:
                continue

            pin_channel = self.bot.get_channel(
                channel_id
            ) or await self.bot.fetch_channel(channel_id)
            assert isinstance(pin_channel, discord.TextChannel)
            new_pin = await pin_new_ssl(embed, pin_channel)
            topic = f"[{current_time.strftime("%m.%d.%y")}] {artist_name} - {song_name}"
            if pin_role := pin_roles.get(guild_id):
                await pin_channel.send(f"<@&{pin_role}> {topic}")
            else:
                await pin_channel.send(topic)
            await pin_channel.edit(topic=topic)
            await unpin_old_ssl(
                embed.title,
                pin_channel,
                new_pin,
            )

        self.bot.ssleague[game][artist_name]["date"] = current_time.strftime(
            game_details["dateFormat"]
        )
        self.bot.ssleague[game][artist_name]["songs"][str(song_id)] = (
            current_time.strftime(game_details["dateFormat"])
        )

    @pin_ssls.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: "dBot") -> None:
    await bot.add_cog(PinSSLeague(bot))
