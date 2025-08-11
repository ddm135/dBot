# pyright: reportTypedDictNotRequiredAccess=false

import asyncio
import gzip
import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import aiohttp
import discord
from discord.ext import commands
from google.auth.transport import requests
from google.oauth2.service_account import IDTokenCredentials

from statics.consts import GAMES, AssetScheme

from .embeds import SSLeagueEmbed as _SSLeagueEmbed
from .types import SuperStarHeaders

if TYPE_CHECKING:
    from dBot import dBot
    from statics.types import BasicDetails


class SuperStar(commands.Cog):
    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def get_a_json(self, basic_details: "BasicDetails") -> dict:
        headers = SuperStarHeaders()
        iv = headers["X-SuperStar-AES-IV"]

        async with aiohttp.ClientSession() as session:
            cog = self.bot.get_cog("Cryptographic")

            async with session.post(
                url=basic_details["manifest"]["ServerUrl"],
                headers=headers,
                data=cog.encrypt_cbc(  # type: ignore[union-attr]
                    '{"class":"Platform","method":"checkAssetBundle","params":[0]}', iv
                ),
            ) as r:
                ajs = await self.read_dalcom_json(r, iv)
        return ajs

    async def login_classic(
        self, basic_details: "BasicDetails", credentials: dict
    ) -> tuple[int, str]:
        headers = SuperStarHeaders()
        iv = headers["X-SuperStar-AES-IV"]

        async with aiohttp.ClientSession() as session:
            cog = self.bot.get_cog("Cryptographic")

            async with session.post(
                url=basic_details["manifest"]["ServerUrl"],
                headers=headers,
                data=cog.encrypt_cbc(  # type: ignore[union-attr]
                    credentials["account"].format(
                        version=basic_details["version"],
                        **credentials,
                    ),
                    iv,
                ),
            ) as r:
                account = await self.read_dalcom_json(r, iv)

        oid = account["result"]["user"]["objectID"]
        key = account["invoke"][0]["params"][0]
        return oid, key

    async def login_google(
        self, basic_details: "BasicDetails", credentials: dict, target_audience: str
    ) -> tuple[int, str]:
        gredentials = IDTokenCredentials.from_service_account_file(
            filename=credentials["service_account"],
            target_audience=f"{target_audience}.apps.googleusercontent.com",
        )
        gredentials.refresh(requests.Request())
        id_token = gredentials.token

        headers = SuperStarHeaders()
        iv = headers["X-SuperStar-AES-IV"]

        async with aiohttp.ClientSession() as session:
            cog = self.bot.get_cog("Cryptographic")

            async with session.post(
                url=basic_details["manifest"]["ServerUrl"],
                headers=headers,
                data=cog.encrypt_cbc(  # type: ignore[union-attr]
                    credentials["account"].format(
                        version=basic_details["version"],
                        id_token=id_token,
                        **credentials,
                    ),
                    iv,
                ),
            ) as r:
                account = await self.read_dalcom_json(r, iv)

        oid = account["result"]["user"]["objectID"]
        key = account["invoke"][0]["params"][0]
        return oid, key

    async def login_dalcom(
        self, basic_details: "BasicDetails", credentials: dict, authorization: str
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

            cog = self.bot.get_cog("Cryptographic")

            async with session.post(
                url=basic_details["manifest"]["ServerUrl"],
                headers=headers,
                data=cog.encrypt_cbc(  # type: ignore[union-attr]
                    credentials["account"].format(
                        version=basic_details["version"],
                        access_token=access_token,
                        **credentials,
                    ),
                    iv,
                ),
            ) as r:
                account = await self.read_dalcom_json(r, iv)

        oid = account["result"]["user"]["objectID"]
        key = account["invoke"][0]["params"][0]
        return oid, key

    async def get_ssleague(
        self, basic_details: "BasicDetails", oid: int, key: str
    ) -> dict:
        headers = SuperStarHeaders()
        iv = headers["X-SuperStar-AES-IV"]

        async with aiohttp.ClientSession() as session:
            cog = self.bot.get_cog("Cryptographic")

            async with session.post(
                url=basic_details["manifest"]["ServerUrl"],
                headers=headers,
                data=cog.encrypt_cbc(  # type: ignore[union-attr]
                    f'{{"class":"StarLeague",'
                    f'"method":"getWeekPlayMusic",'
                    f'"params":[{oid},"{key}"]}}',
                    iv,
                ),
            ) as r:
                ssleague = await self.read_dalcom_json(r, iv)
        return ssleague

    async def read_dalcom_json(
        self, response: aiohttp.ClientResponse, iv: str | bytes
    ) -> dict:
        try:
            result = await response.json(content_type=None)
        except json.JSONDecodeError:
            cog = self.bot.get_cog("Cryptographic")
            result = json.loads(
                cog.decrypt_cbc(  # type: ignore[union-attr]
                    await response.text(),
                    iv,
                )
            )
        return result

    async def get_data(self, url: str) -> list[dict]:
        async with aiohttp.ClientSession() as session:
            async with session.get(url=url) as r:
                content = await r.read()

        cog = self.bot.get_cog("Cryptographic")
        return json.loads(
            cog.decrypt_ecb(  # type: ignore[union-attr]
                gzip.decompress(content)
            ).replace(rb"\/", rb"/")
        )

    async def get_file(
        self, game: str, data_type: Literal["grd", "msd"], item_id: str, file_key: str
    ) -> str | discord.File | None:
        data = getattr(self.bot, f"{data_type}").get(game, [])
        for item in data:
            if item["code"] == item_id:
                file_url = item[file_key]
                break
        else:
            return None

        if GAMES[game]["assetScheme"] == AssetScheme.JSON_URL:
            url_data = self.bot.url[game]
            for url in url_data:
                if url["code"] == file_url:
                    return url["url"]
            return None
        elif GAMES[game]["assetScheme"] in (
            AssetScheme.BINARY_CATALOG,
            AssetScheme.JSON_CATALOG,
        ) and (catalog := self.bot.basic[game].get("catalog")):
            catalog_key = file_url
            file_path = Path(f"data/assets/{game}/{file_url}")
            if not file_path.exists():
                file_path.parent.mkdir(parents=True, exist_ok=True)
                while dependency := catalog[catalog_key]["dependency"]:
                    catalog_key = dependency
                bundle_path = Path(f"data/bundles/{game}/{catalog_key}")
                bundle_extract_path = bundle_path.with_suffix("")
                bundle_extract_path.mkdir(parents=True, exist_ok=True)

                if not any(bundle_extract_path.iterdir()):
                    if not bundle_path.exists():
                        async with aiohttp.ClientSession() as session:
                            async with session.get(
                                catalog[catalog_key]["internalId"]
                            ) as r:
                                with open(bundle_path, "wb") as f:
                                    f.write(await r.read())
                    process = await asyncio.create_subprocess_exec(
                        "utils/bundle",
                        str(bundle_path),
                        str(bundle_extract_path),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await process.communicate()

                file_extract_path = bundle_extract_path / "Assets" / file_url
                shutil.copyfile(file_extract_path, file_path)

            return discord.File(file_path)

        return file_url

    @staticmethod
    async def pin_new_ssl(
        embed: discord.Embed,
        pin_channel: discord.TextChannel,
    ) -> int:
        msg = await pin_channel.send(embed=embed)
        await asyncio.sleep(1)
        await msg.pin()
        return msg.id

    @staticmethod
    async def unpin_old_ssl(
        embed_title: str | None, pin_channel: discord.TextChannel, new_pin: int
    ) -> None:
        if embed_title is None:
            return

        pins = await pin_channel.pins()
        for pin in pins:
            if pin.id == new_pin:
                continue

            embeds = pin.embeds
            if embeds and embeds[0].title and embed_title in embeds[0].title:
                await pin.unpin()
                break

    class SSLeagueEmbed(_SSLeagueEmbed):
        pass


async def setup(bot: "dBot") -> None:
    await bot.add_cog(SuperStar(bot))
