# mypy: disable-error-code="literal-required"

import asyncio
import gzip
import inspect
import json
import logging
from datetime import time, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import aiohttp
from discord.ext import commands, tasks

from static.dConsts import A_JSON_BODY, A_JSON_HEADERS, TIMEZONES
from static.dHelpers import (
    decrypt_cbc,
    decrypt_ecb,
    get_column_letter,
    get_sheet_data,
    jsondict_str2int,
)
from static.dTypes import GameDetails

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
        self.bot.games.clear()
        self.bot.info_by_name.clear()
        self.bot.info_by_id.clear()
        self.bot.info_color.clear()
        await super().cog_unload()

    @tasks.loop(time=time(hour=12, tzinfo=TIMEZONES["KST"]))
    async def info_sync(self) -> None:
        self.bot.info_data_ready = False
        await asyncio.sleep(5)
        self.LOGGER.info("Downloading game data...")
        self.bot.games.clear()
        self.bot.info_by_name.clear()
        self.bot.info_by_id.clear()
        self.bot.info_color.clear()

        game_attr = inspect.get_annotations(GameDetails)
        games = get_sheet_data(
            "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
            f"Games!A2:{get_column_letter(len(game_attr) - 1)}",
        )
        for key, *details in games:
            vals = zip(game_attr, game_attr.values(), details)
            for val in vals:
                if val[1] == str:
                    self.bot.games[key][val[0]] = val[2]
                elif val[1] == tuple[str, ...]:
                    self.bot.games[key][val[0]] = tuple(val[2].split(","))
                elif val[1] == int:
                    self.bot.games[key][val[0]] = int(val[2], 16)
                elif val[1] == ZoneInfo:
                    self.bot.games[key][val[0]] = TIMEZONES[val[2]]
                elif val[1] == timedelta:
                    self.bot.games[key][val[0]] = timedelta(hours=int(val[2]))
                else:
                    self.bot.games[key][val[0]] = json.loads(
                        val[2], object_hook=jsondict_str2int
                    )

        self.LOGGER.info("Downloading song data...")
        for game, game_details in self.bot.games.items():
            if not game_details["pinChannelIds"]:
                continue

            info = get_sheet_data(
                game_details["infoId"],
                game_details["infoSongs"],
                "KR" if game_details["timezone"] == TIMEZONES["KST"] else None,
            )
            for row in info:
                _row = tuple(row)
                self.bot.info_by_name[game][
                    row[game_details["infoColumns"].index("artist_name")]
                ][row[game_details["infoColumns"].index("song_name")]] = _row
                if "song_id" in game_details["infoColumns"]:
                    self.bot.info_by_id[game][
                        row[game_details["infoColumns"].index("song_id")]
                    ] = _row

            self.bot.info_color[game] = await self.get_music_data(game_details["api"])

    async def get_a_json(self, api_url: str) -> dict[str, Any]:
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
