import asyncio
import gzip
import json
import logging
from datetime import time
from typing import TYPE_CHECKING

import aiohttp
from discord.ext import commands, tasks

from static.dConsts import A_JSON_BODY, A_JSON_HEADERS, GAMES, TIMEZONES
from static.dHelpers import decrypt_cbc, decrypt_ecb, get_sheet_data

if TYPE_CHECKING:
    from dBot import dBot


class InfoSync(commands.Cog):
    LOGGER = logging.getLogger(__name__)

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await self.info_sync()
        self.bot.info_data_ready = True
        self.info_sync.start()
        await super().cog_load()

    async def cog_unload(self) -> None:
        self.bot.info_data_ready = False
        self.info_sync.cancel()
        self.bot.info_by_name.clear()
        await super().cog_unload()

    @tasks.loop(time=time(hour=12, tzinfo=TIMEZONES["KST"]))
    async def info_sync(self) -> None:
        self.bot.info_data_ready = False
        await asyncio.sleep(5)
        self.LOGGER.info("Downloading song data...")
        self.bot.info_by_name.clear()
        for game, game_details in GAMES.items():
            if not game_details["pinChannelIds"]:
                continue

            info = get_sheet_data(
                game_details["infoId"],
                game_details["infoSongs"],
            )
            for row in info:
                self.bot.info_by_name[game][
                    row[game_details["infoColumns"].index("artist_name")]
                ][row[game_details["infoColumns"].index("song_name")]] = row
                self.bot.info_by_id[game][
                    row[game_details["infoColumns"].index("song_id")]
                ] = row

        self.bot.info_color[game] = await self.get_music_data(
            game_details["api"]
        )

    async def get_a_json(self, api_url: str) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url=api_url,
                headers=A_JSON_HEADERS,
                data=A_JSON_BODY,
            ) as r:
                try:
                    ajs = await r.json(content_type=None)
                except json.JSONDecodeError:
                    ajs = json.loads(decrypt_cbc(await r.text()))
        return ajs

    async def get_music_data(self, api_url: str) -> list[dict]:
        ajs = await self.get_a_json(api_url)
        msd_url = ajs["result"]["context"]["MusicData"]["file"]
        async with aiohttp.ClientSession() as session:
            async with session.get(url=msd_url) as r:
                msd_enc = b""
                while True:
                    chunk = await r.content.read(1024)
                    if not chunk:
                        break
                    msd_enc += chunk

        msd_js = json.loads(
            decrypt_ecb(gzip.decompress(msd_enc))
            .replace(rb"\/", rb"/")
            .replace(rb"\u", rb"ddm135-u")
        )
        return json.loads(
            json.dumps(msd_js, indent="\t", ensure_ascii=False)
            .replace(r"ddm135-u", r"\u")
            .encode()
        )

    @info_sync.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()

    @info_sync.after_loop
    async def after_loop(self) -> None:
        if not self.info_sync.is_being_cancelled():
            await asyncio.sleep(5)
            self.bot.info_data_ready = True


async def setup(bot: "dBot") -> None:
    await bot.add_cog(InfoSync(bot))
