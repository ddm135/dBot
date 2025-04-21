import asyncio
import json
from datetime import datetime, time
from typing import TYPE_CHECKING

import aiohttp
import discord
from discord.ext import commands, tasks
from google.auth.transport import requests
from google.oauth2.service_account import IDTokenCredentials
from packaging.version import Version

from statics.consts import CREDENTIALS_DATA, GAMES, SUPERSTAR_HEADERS
from statics.helpers import (
    encrypt_cbc,
    generate_ssl_embed,
    get_ss_json,
    pin_new_ssl,
    unpin_old_ssl,
)

if TYPE_CHECKING:
    from dBot import dBot
    from statics.types import GameDetails


class PinSSL(commands.Cog):

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.pin_ssls.start()
        await super().cog_load()

    async def cog_unload(self) -> None:
        self.pin_ssls.cancel()
        await super().cog_unload()

    @tasks.loop(minutes=1)
    async def pin_ssls(self) -> None:
        with open(CREDENTIALS_DATA, "r") as f:
            all_credentials = json.load(f)

        tasks = [
            self.pin_ssl(game, game_details, all_credentials[game])
            for game, game_details in GAMES.items()
            if game_details["pinChannelIds"] and game in all_credentials
        ]
        await asyncio.gather(*tasks)

        with open(CREDENTIALS_DATA, "w") as f:
            json.dump(all_credentials, f, indent=4)

    async def pin_ssl(
        self, game: str, game_details: "GameDetails", credentials: dict
    ) -> None:
        timezone = game_details["timezone"]
        offset = game_details["resetOffset"]
        current_time = datetime.now(tz=timezone) - offset
        # if current_time.hour != 0:
        #     return

        apiUrl = game_details["api"]
        credentials["version"] = await self.get_active_version(credentials)
        if credentials["isSNS"]:
            if credentials["provider"] == 0:
                oid, key = await self.login_google(apiUrl, credentials)
            elif credentials["provider"] == 3:
                oid, key = await self.login_dalcom_id(apiUrl, credentials)
            else:
                return
        else:
            oid, key = await self.login(apiUrl, credentials)
        ssleague = await self.get_ssleague(apiUrl, oid, key)

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

        artist_name = (
            ssl_song[artist_name_index].replace(r"*", r"\*").replace(r"_", r"\_")
        )
        song_name = ssl_song[song_name_index].replace(r"*", r"\*").replace(r"_", r"\_")
        duration = ssl_song[duration_index]
        skills = ssl_song[skills_index] if skills_index is not None else None

        color = game_details["color"]
        image_url = None

        msd_data = self.bot.info_msd[game]
        for song in msd_data:
            if song["code"] == song_id:
                color = int(song["albumBgColor"][:-2], 16)
                image_url = song["album"]
                break

        if game_details["legacyUrlScheme"]:
            url_data = self.bot.info_url[game]
            for url in url_data:
                if url["code"] == image_url:
                    image_url = url["url"]
                    break

        embed = generate_ssl_embed(
            artist_name,
            song_name,
            duration,
            image_url,
            color,
            skills,
            current_time,
            self.bot.user.name,  # type: ignore[union-attr]
        )

        pin_channels = game_details["pinChannelIds"]
        pin_roles = game_details["pinRoles"]
        for guild_id, channel_id in pin_channels.items():
            if not channel_id:
                continue

            pin_channel = self.bot.get_channel(channel_id)
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

    async def get_active_version(self, credentials: dict) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url=credentials["manifest"].format(**credentials),
            ) as r:
                manifest = await r.json(content_type=None)
                return str(
                    max(
                        Version(credentials["version"]),
                        Version(manifest["ActiveVersion_Android"]),
                        Version(manifest["ActiveVersion_IOS"]),
                    )
                )

    async def login(self, apiUrl: str, credentials: dict) -> tuple[int, str]:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url=apiUrl,
                headers=SUPERSTAR_HEADERS,
                data=encrypt_cbc(credentials["account"].format(**credentials)),
            ) as r:
                account = await get_ss_json(r)

        oid = account["result"]["user"]["objectID"]
        key = account["invoke"][0]["params"][0]
        return oid, key

    async def login_google(self, apiUrl: str, credentials: dict) -> tuple[int, str]:
        gCredentials = IDTokenCredentials.from_service_account_file(
            filename=credentials["service_account"],
            target_audience=credentials["target_audience"],
        )
        gCredentials.refresh(requests.Request())
        id_token = gCredentials.token

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url=apiUrl,
                headers=SUPERSTAR_HEADERS,
                data=encrypt_cbc(
                    credentials["account"].format(id_token=id_token, **credentials)
                ),
            ) as r:
                account = await get_ss_json(r)

        oid = account["result"]["user"]["objectID"]
        key = account["invoke"][0]["params"][0]
        return oid, key

    async def login_dalcom_id(self, apiUrl: str, credentials: dict) -> tuple[int, str]:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url="https://oauth.dalcomsoft.net/v1/token",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Basic {credentials["authorization"]}",
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
                headers=SUPERSTAR_HEADERS,
                data=encrypt_cbc(
                    credentials["account"].format(
                        access_token=access_token, **credentials
                    )
                ),
            ) as r:
                account = await get_ss_json(r)

        oid = account["result"]["user"]["objectID"]
        key = account["invoke"][0]["params"][0]
        return oid, key

    async def get_ssleague(self, apiUrl: str, oid: int, key: str) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url=apiUrl,
                headers=SUPERSTAR_HEADERS,
                data=encrypt_cbc(
                    f'{"{"}"class":"StarLeague","method":"getWeekPlayMusic",'
                    f'"params":[{oid},"{key}"]{"}"}'
                ),
            ) as r:
                ssleague = await get_ss_json(r)
        return ssleague

    @pin_ssls.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: "dBot") -> None:
    await bot.add_cog(PinSSL(bot))
