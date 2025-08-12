# pyright: reportTypedDictNotRequiredAccess=false

import asyncio
import logging
from datetime import datetime, time
from typing import TYPE_CHECKING

import aiohttp
import discord
import discord.backoff
from discord.ext import commands, tasks

from statics.consts import GAMES, RESET_OFFSET, Data, InfoColumns

if TYPE_CHECKING:
    from dBot import dBot


class PinSSLeague(commands.Cog):
    LOGGER = logging.getLogger(__name__.rpartition(".")[0])

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.pin_ssls.start()

    async def cog_unload(self) -> None:
        self.pin_ssls.cancel()

    @tasks.loop(time=[time(hour=h) for h in range(24)])
    async def pin_ssls(self) -> None:
        cog = self.bot.get_cog("DataSync")
        cog.save_last_appearance()  # type: ignore[union-attr]

        pin_tasks = [
            self.pin_ssl(game, self.bot.credentials[game])
            for game, game_details in GAMES.items()
            if {"info", "pinChannelIds"} <= set(game_details)
            and game in self.bot.credentials
        ]
        await asyncio.gather(*pin_tasks, return_exceptions=True)

        cog.save_data(Data.SSLEAGUES)  # type: ignore[union-attr]

    async def pin_ssl(self, game: str, credentials: dict) -> None:
        game_details = GAMES[game]
        timezone = game_details["timezone"]
        current_time = datetime.now(tz=timezone) - RESET_OFFSET
        if current_time.hour:
            return
        backoff = discord.backoff.ExponentialBackoff()
        cog = self.bot.get_cog("SuperStar")

        while True:
            try:
                match credentials["provider"]:
                    case 0 | 1 if not credentials["isSNS"]:
                        oid, key = await cog.login_classic(  # type: ignore[union-attr]
                            self.bot.basic[game], credentials
                        )
                    case 0 if credentials["isSNS"] and (
                        target_audience := game_details.get("target_audience")
                    ):
                        oid, key = await cog.login_google(  # type: ignore[union-attr]
                            self.bot.basic[game], credentials, target_audience
                        )
                    case 3 if credentials["isSNS"] and (
                        authorization := game_details.get("authorization")
                    ):
                        oid, key = await cog.login_dalcom(  # type: ignore[union-attr]
                            self.bot.basic[game], credentials, authorization
                        )
                    case _:
                        return
                ssleague = await cog.get_ssleague(  # type: ignore[union-attr]
                    self.bot.basic[game], oid, key
                )
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
        duration_index = info_columns.index("duration")
        skills_index = (
            info_columns.index("skills")
            if game_details["info"]["columns"] == InfoColumns.SSL_WITH_SKILLS.value
            else None
        )

        artist_name = ssl_song[artist_name_index]
        song_name = ssl_song[song_name_index]
        duration = ssl_song[duration_index]
        skills = ssl_song[skills_index] if skills_index is not None else None

        results = await cog.get_attributes(  # type: ignore[union-attr]
            game,
            "msd",
            song_id,
            {"albumBgColor": False, "album": True},
        )
        color = (
            int(results["albumBgColor"][:-2], 16)
            if results["albumBgColor"]
            else game_details["color"]
        )
        album = results["album"]
        icon = self.bot.emblem[game][artist_name]

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

        embed = cog.SSLeagueEmbed(  # type: ignore[union-attr]
            artist_name,
            song_name,
            duration,
            album,
            icon,
            color,
            skills,
            current_time,
            self.bot.user.name if self.bot.user else self.bot.__class__.__name__,
            artist_last,
            song_last,
        )

        files = []
        for image in (album, icon):
            if isinstance(image, discord.File):
                files.append(image)
        pin_channels = game_details["pinChannelIds"]
        pin_roles = game_details["pinRoles"]
        for guild_id, channel_id in pin_channels.items():
            if not channel_id:
                continue

            pin_channel = self.bot.get_channel(
                channel_id
            ) or await self.bot.fetch_channel(channel_id)
            assert isinstance(pin_channel, discord.TextChannel)
            new_pin = await cog.pin_new_ssl(  # type: ignore[union-attr]
                embed, pin_channel, files
            )
            topic = f"[{current_time.strftime("%m.%d.%y")}] {artist_name} - {song_name}"
            if pin_role := pin_roles.get(guild_id):
                await pin_channel.send(f"<@&{pin_role}> {topic}")
            else:
                await pin_channel.send(topic)
            await pin_channel.edit(topic=topic)
            await cog.unpin_old_ssl(  # type: ignore[union-attr]
                embed.title, pin_channel, new_pin
            )

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
