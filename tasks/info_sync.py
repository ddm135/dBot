import gzip
import json
import logging
from datetime import datetime, time
from typing import TYPE_CHECKING, Any

import aiohttp
from discord.ext import commands, tasks

from statics.consts import A_JSON_BODY, GAMES, SUPERSTAR_HEADERS, TIMEZONES
from statics.helpers import decrypt_cbc, decrypt_ecb, get_sheet_data

if TYPE_CHECKING:
    from dBot import dBot


class InfoSync(commands.Cog):
    LOGGER = logging.getLogger(__name__)

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await self.info_sync()
        self.info_sync.start()
        await super().cog_load()

    async def cog_unload(self) -> None:
        self.bot.info_data_ready = False
        self.info_sync.cancel()
        self.bot.info_ajs.clear()
        self.bot.info_msd.clear()
        self.bot.info_url.clear()
        self.bot.info_by_name.clear()
        self.bot.info_by_id.clear()
        await super().cog_unload()

    @tasks.loop(time=time(hour=10, tzinfo=TIMEZONES["KST"]))
    async def info_sync(self) -> None:
        if self.bot.info_data_ready and datetime.now().weekday() != 0:
            return

        self.bot.info_data_ready = False
        self.LOGGER.info("Downloading song data...")

        for game, game_details in GAMES.items():
            self.bot.info_ajs[game].clear()
            ajs = self.bot.info_ajs[game] = await self.get_a_json(game_details["api"])
            if ajs["code"] != 1000:
                self.LOGGER.info(
                    f"{game_details["name"]} server is unavailable. Skipping..."
                )
                continue

            self.bot.info_msd[game].clear()
            self.bot.info_by_name[game].clear()
            self.bot.info_by_id[game].clear()

            self.bot.info_msd[game] = await self.get_music_data(ajs)
            if game_details["legacyUrlScheme"]:
                self.bot.info_url[game].clear()
                self.bot.info_url[game] = await self.get_url_data(ajs)

            if not game_details["infoId"]:
                continue

            info = get_sheet_data(
                game_details["infoId"],
                game_details["infoRange"],
                "KR" if game_details["timezone"] == TIMEZONES["KST"] else None,
            )

            info_columns = game_details["infoColumns"]
            artist_name_index = info_columns.index("artist_name")
            song_name_index = info_columns.index("song_name")
            song_id_index = info_columns.index("song_id")
            duration_index = info_columns.index("duration")

            for row in info:
                if not row:
                    continue

                row[duration_index] = (
                    row[duration_index]
                    if ":" in row[duration_index]
                    else f"{int(row[duration_index]) // 60}:"
                    f"{int(row[duration_index]) % 60:02d}"
                )

                self.bot.info_by_name[game][row[artist_name_index]][
                    row[song_name_index]
                ] = row
                self.bot.info_by_id[game][row[song_id_index]] = row

        self.bot.info_data_ready = True

    async def get_a_json(self, api_url: str) -> dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url=api_url,
                headers=SUPERSTAR_HEADERS,
                data=A_JSON_BODY,
            ) as r:
                try:
                    ajs = await r.json(content_type=None)
                except json.JSONDecodeError:
                    ajs = json.loads(decrypt_cbc(await r.text()))
        return ajs

    async def get_music_data(self, ajs: dict[str, Any]) -> list[dict[str, Any]]:
        msd_url = ajs["result"]["context"]["MusicData"]["file"]
        return await self.get_game_data(msd_url)

    async def get_url_data(self, ajs: dict[str, Any]) -> list[dict[str, Any]]:
        url_url = ajs["result"]["context"]["URLs"]["file"]
        return await self.get_game_data(url_url)

    async def get_game_data(self, url: str) -> list[dict[str, Any]]:
        async with aiohttp.ClientSession() as session:
            async with session.get(url=url) as r:
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


async def setup(bot: "dBot") -> None:
    await bot.add_cog(InfoSync(bot))
