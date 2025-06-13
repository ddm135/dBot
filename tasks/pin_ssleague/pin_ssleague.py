import asyncio
import json
import logging
from datetime import datetime, time
from typing import TYPE_CHECKING

import aiohttp
import discord
import discord.backoff
from discord.ext import commands, tasks
from google.auth.transport import requests
from google.oauth2.service_account import IDTokenCredentials
from packaging.version import Version

from statics.consts import CREDENTIALS_DATA, GAMES, RESET_OFFSET, SSLEAGUE_DATA
from statics.helpers import (
    encrypt_cbc,
    get_ss_json,
    pin_new_ssl,
    unpin_old_ssl,
)
from statics.types import SSLeagueEmbed, SuperStarHeaders

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
        for game in self.bot.ssleague_manual:
            target = self.bot.ssleague[game][self.bot.ssleague_manual[game]["artist"]]
            date = self.bot.ssleague_manual[game]["date"]
            target["songs"][self.bot.ssleague_manual[game]["song_id"]] = date
            target["date"] = date
        self.bot.ssleague_manual.clear()

        with open(CREDENTIALS_DATA, "r", encoding="utf-8") as f:
            all_credentials = json.load(f)

        pin_tasks = [
            self.pin_ssl(game, all_credentials[game])
            for game, game_details in GAMES.items()
            if game_details["pinChannelIds"] and game in all_credentials
        ]
        await asyncio.gather(*pin_tasks, return_exceptions=True)

        with open(CREDENTIALS_DATA, "w", encoding="utf-8") as f:
            json.dump(all_credentials, f, indent=4)
        with open(SSLEAGUE_DATA, "w", encoding="utf-8") as f:
            json.dump(self.bot.ssleague, f, indent=4)

    async def pin_ssl(self, game: str, credentials: dict) -> None:
        game_details = GAMES[game]
        timezone = game_details["timezone"]
        current_time = datetime.now(tz=timezone) - RESET_OFFSET
        if current_time.hour != 0:
            return
        apiUrl = game_details["api"]
        backoff = discord.backoff.ExponentialBackoff()

        while True:
            try:
                credentials["version"] = await self.get_active_version(
                    game_details["manifest"], credentials
                )
                match credentials["provider"]:
                    case 0 | 1 if not credentials["isSNS"]:
                        oid, key = await self.login(apiUrl, credentials)
                    case 0 if credentials["isSNS"]:
                        oid, key = await self.login_google(
                            apiUrl, credentials, game_details["target_audience"]
                        )
                    case 3 if credentials["isSNS"]:
                        oid, key = await self.login_dalcom_id(
                            apiUrl, credentials, game_details["authorization"]
                        )
                    case _:
                        return
                ssleague = await self.get_ssleague(apiUrl, oid, key)
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
            self.bot.user.name,  # type: ignore[union-attr]
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
                embed.title,  # type: ignore[arg-type]
                pin_channel,
                new_pin,
            )

        self.bot.ssleague[game][artist_name]["date"] = current_time.strftime(
            game_details["dateFormat"]
        )
        self.bot.ssleague[game][artist_name]["songs"][str(song_id)] = (
            current_time.strftime(game_details["dateFormat"])
        )

    @staticmethod
    async def get_active_version(manifestUrl: str, credentials: dict) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url=manifestUrl.format(version=credentials["version"]),
            ) as r:
                manifest = await r.json(content_type=None)
                return str(
                    max(
                        Version(credentials["version"]),
                        Version(manifest["ActiveVersion_Android"]),
                        Version(manifest["ActiveVersion_IOS"]),
                    )
                )

    @staticmethod
    async def login(apiUrl: str, credentials: dict) -> tuple[int, str]:
        headers = SuperStarHeaders()
        iv = headers["X-SuperStar-AES-IV"]

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url=apiUrl,
                headers=headers,
                data=encrypt_cbc(credentials["account"].format(**credentials), iv),
            ) as r:
                account = await get_ss_json(r, iv)

        oid = account["result"]["user"]["objectID"]
        key = account["invoke"][0]["params"][0]
        return oid, key

    @staticmethod
    async def login_google(
        apiUrl: str, credentials: dict, target_audience: str
    ) -> tuple[int, str]:
        gCredentials = IDTokenCredentials.from_service_account_file(
            filename=credentials["service_account"],
            target_audience=f"{target_audience}.apps.googleusercontent.com",
        )
        gCredentials.refresh(requests.Request())
        id_token = gCredentials.token

        headers = SuperStarHeaders()
        iv = headers["X-SuperStar-AES-IV"]

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url=apiUrl,
                headers=headers,
                data=encrypt_cbc(
                    credentials["account"].format(id_token=id_token, **credentials), iv
                ),
            ) as r:
                account = await get_ss_json(r, iv)

        oid = account["result"]["user"]["objectID"]
        key = account["invoke"][0]["params"][0]
        return oid, key

    @staticmethod
    async def login_dalcom_id(
        apiUrl: str, credentials: dict, authorization: str
    ) -> tuple[int, str]:
        headers = SuperStarHeaders()
        iv = headers["X-SuperStar-AES-IV"]

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url="https://oauth.dalcomsoft.net/v1/token",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Basic {authorization}",
                },
                data=(
                    f'{{"id":"{credentials["id"]}",'
                    f'"pass":"{credentials["pass"]}",'
                    f'"grant_type":"password"}}'
                ),
            ) as r:
                dalcom_id = await r.json(content_type=None)
                access_token = dalcom_id["data"]["access_token"]

            async with session.post(
                url=apiUrl,
                headers=headers,
                data=encrypt_cbc(
                    credentials["account"].format(
                        access_token=access_token, **credentials
                    ),
                    iv,
                ),
            ) as r:
                account = await get_ss_json(r, iv)

        oid = account["result"]["user"]["objectID"]
        key = account["invoke"][0]["params"][0]
        return oid, key

    @staticmethod
    async def get_ssleague(apiUrl: str, oid: int, key: str) -> dict:
        headers = SuperStarHeaders()
        iv = headers["X-SuperStar-AES-IV"]

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url=apiUrl,
                headers=headers,
                data=encrypt_cbc(
                    f'{{"class":"StarLeague",'
                    f'"method":"getWeekPlayMusic",'
                    f'"params":[{oid},"{key}"]}}',
                    iv,
                ),
            ) as r:
                ssleague = await get_ss_json(r, iv)
        return ssleague

    @pin_ssls.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: "dBot") -> None:
    await bot.add_cog(PinSSLeague(bot))
