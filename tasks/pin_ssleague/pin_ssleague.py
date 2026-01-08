# mypy: disable-error-code="assignment"
# pyright: reportAssignmentType=false, reportTypedDictNotRequiredAccess=false

import asyncio
import json
import logging
from datetime import datetime, time
from pathlib import Path
from typing import TYPE_CHECKING

import aiohttp
import discord
import discord.backoff
from discord.ext import commands, tasks

from statics.consts import GAMES, RESET_OFFSET, Data, InfoColumns

if TYPE_CHECKING:
    from dBot import dBot
    from helpers.superstar import SuperStar
    from tasks.data_sync import DataSync


class PinSSLeague(commands.Cog):
    LOGGER = logging.getLogger(__name__.rpartition(".")[0])

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.pin_ssls.start()

    async def cog_unload(self) -> None:
        self.pin_ssls.cancel()

    @tasks.loop(time=[time(hour=h, minute=15) for h in range(24)])
    async def pin_ssls(self) -> None:
        cog: "DataSync" = self.bot.get_cog("DataSync")
        cog.save_last_appearance()

        with open(Data.CREDENTIALS.value, "r", encoding="utf-8") as f:
            credentials = json.load(f)
        pin_tasks = [
            self.pin_ssl(game, credentials[game])
            for game in GAMES
            if game in credentials
        ]
        await asyncio.gather(*pin_tasks, return_exceptions=True)

        cog.save_data(Data.SSLEAGUES)

    async def pin_ssl(self, game: str, credentials: dict) -> None:
        game_details = GAMES[game]
        timezone = game_details["timezone"]
        current_time = datetime.now(tz=timezone) - RESET_OFFSET
        if current_time.hour:
            return
        backoff = discord.backoff.ExponentialBackoff()
        cog: "SuperStar" = self.bot.get_cog("SuperStar")

        while True:
            try:
                match credentials["provider"]:
                    case 0 | 1 if not credentials["isSNS"]:
                        oid, key = await cog.login_classic(game, credentials)
                    case 0 if credentials["isSNS"] and (
                        target_audience := game_details.get("target_audience")
                    ):
                        oid, key = await cog.login_google(
                            game, credentials, target_audience
                        )
                    case 3 if credentials["isSNS"] and (
                        authorization := game_details.get("authorization")
                    ):
                        oid, key = await cog.login_dalcom(
                            game, credentials, authorization
                        )
                    case _:
                        return
                ssleague = await cog.get_ssleague(game, oid, key)
            except aiohttp.ClientError as e:
                self.LOGGER.exception(str(e))
                await asyncio.sleep(backoff.delay())
            except Exception as e:
                self.LOGGER.exception(str(e))
                return
            else:
                break

        curday = ssleague["result"]["curday"]
        music_list = ssleague["result"]["musicList"]
        music = next(music for music in music_list if music["day"] == curday)
        song_id = music["music"]
        if not (ssl_song := self.bot.info_by_id[game].get(str(song_id))):
            return

        info_columns = game_details["info"]["columns"]
        artist_name_index = info_columns.index("artist_name")
        song_name_index = info_columns.index("song_name")
        skills_index = (
            info_columns.index("skills")
            if game_details["info"]["columns"] == InfoColumns.SKILLS.value
            else None
        )

        artist_name = ssl_song[artist_name_index]
        song_name = ssl_song[song_name_index]
        duration = self.bot.info_from_file[game][str(song_id)]["sound"]["duration"]
        note_count = self.bot.info_from_file[game][str(song_id)]["seq"]
        skills = ssl_song[skills_index] if skills_index is not None else None

        results = await cog.get_attributes(
            game, "MusicData", song_id, {"albumBgColor": False, "album": True}
        )
        color = (
            int(results["albumBgColor"][:-2], 16)
            if results["albumBgColor"]
            else game_details["color"]
        )
        album = results["album"]
        icon = self.bot.artist[game][artist_name]["emblem"]

        artist_last_str = self.bot.ssleagues[game][artist_name]["date"]
        if artist_last_str:
            artist_last = datetime.strptime(artist_last_str, game_details["dateFormat"])
            artist_last = artist_last.replace(
                tzinfo=timezone, hour=2, minute=0, second=0, microsecond=0
            )
        else:
            artist_last = None
        song_last_str = self.bot.ssleagues[game][artist_name]["songs"][str(song_id)]
        if song_last_str:
            song_last = datetime.strptime(song_last_str, game_details["dateFormat"])
            song_last = song_last.replace(
                tzinfo=timezone, hour=2, minute=0, second=0, microsecond=0
            )
        else:
            song_last = None

        embed = cog.SSLeagueEmbed(
            game,
            artist_name,
            song_name,
            duration,
            note_count,
            album,
            icon,
            color,
            skills,
            current_time,
            self.bot.user.name if self.bot.user else self.bot.__class__.__name__,
            artist_last,
            song_last,
        )

        files = [
            discord.File(file, filename=filename)
            for filename, file in {
                "album.png": album,
                "icon.png": icon,
            }.items()
            if isinstance(file, Path)
        ]
        pin_channels = game_details["pinChannelIds"]
        pin_roles = game_details["pinRoles"]
        topic = f"[{current_time.strftime("%m.%d.%y")}] {artist_name} - {song_name}"
        for guild_id, channel_id in pin_channels.items():
            if not channel_id:
                continue

            pin_channel = self.bot.get_channel(
                channel_id
            ) or await self.bot.fetch_channel(channel_id)
            assert isinstance(pin_channel, discord.TextChannel)
            new_pin = await cog.pin_new_ssl(embed, pin_channel, files)
            if pin_role := pin_roles.get(guild_id):
                await pin_channel.send(f"<@&{pin_role}> {topic}")
            else:
                await pin_channel.send(topic)
            await pin_channel.edit(topic=topic)
            await cog.unpin_old_ssl(embed, pin_channel, new_pin)

        self.bot.ssleagues[game][artist_name]["date"] = current_time.strftime(
            game_details["dateFormat"]
        )
        self.bot.ssleagues[game][artist_name]["songs"][str(song_id)] = (
            current_time.strftime(game_details["dateFormat"])
        )

    @pin_ssls.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: "dBot") -> None:
    await bot.add_cog(PinSSLeague(bot))
