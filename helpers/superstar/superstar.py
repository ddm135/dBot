# mypy: disable-error-code="union-attr"
# pyright: reportAttributeAccessIssue=false, reportOptionalMemberAccess=false

import asyncio
import gzip
import json
from typing import TYPE_CHECKING

import aiohttp
import discord
from discord.ext import commands
from google.auth.transport import requests
from google.oauth2.service_account import IDTokenCredentials
from packaging.version import Version

from .embeds import SSLeagueEmbed as _SSLeagueEmbed
from .types import SuperStarHeaders

if TYPE_CHECKING:
    from dBot import dBot


class SuperStar(commands.Cog):
    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    @staticmethod
    async def get_active_version(manifest_url: str, credentials: dict) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url=manifest_url.format(version=credentials["version"]),
            ) as r:
                manifest = await r.json(content_type=None)
                return str(
                    max(
                        Version(credentials["version"]),
                        Version(manifest["ActiveVersion_Android"]),
                        Version(manifest["ActiveVersion_IOS"]),
                    )
                )

    async def get_a_json(self, api_url: str) -> dict:
        headers = SuperStarHeaders()
        iv = headers["X-SuperStar-AES-IV"]

        async with aiohttp.ClientSession() as session:
            cog = self.bot.get_cog("Cryptographic")

            async with session.post(
                url=api_url,
                headers=headers,
                data=cog.encrypt_cbc(
                    '{"class":"Platform","method":"checkAssetBundle","params":[0]}', iv
                ),
            ) as r:
                ajs = await self.read_json(r, iv)
        return ajs

    async def login_classic(self, api_url: str, credentials: dict) -> tuple[int, str]:
        headers = SuperStarHeaders()
        iv = headers["X-SuperStar-AES-IV"]

        async with aiohttp.ClientSession() as session:
            cog = self.bot.get_cog("Cryptographic")

            async with session.post(
                url=api_url,
                headers=headers,
                data=cog.encrypt_cbc(credentials["account"].format(**credentials), iv),
            ) as r:
                account = await self.read_json(r, iv)

        oid = account["result"]["user"]["objectID"]
        key = account["invoke"][0]["params"][0]
        return oid, key

    async def login_google(
        self, api_url: str, credentials: dict, target_audience: str
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
                url=api_url,
                headers=headers,
                data=cog.encrypt_cbc(
                    credentials["account"].format(id_token=id_token, **credentials), iv
                ),
            ) as r:
                account = await self.read_json(r, iv)

        oid = account["result"]["user"]["objectID"]
        key = account["invoke"][0]["params"][0]
        return oid, key

    async def login_dalcom_id(
        self, api_url: str, credentials: dict, authorization: str
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
                url=api_url,
                headers=headers,
                data=cog.encrypt_cbc(
                    credentials["account"].format(
                        access_token=access_token, **credentials
                    ),
                    iv,
                ),
            ) as r:
                account = await self.read_json(r, iv)

        oid = account["result"]["user"]["objectID"]
        key = account["invoke"][0]["params"][0]
        return oid, key

    async def get_ssleague(self, api_url: str, oid: int, key: str) -> dict:
        headers = SuperStarHeaders()
        iv = headers["X-SuperStar-AES-IV"]

        async with aiohttp.ClientSession() as session:
            cog = self.bot.get_cog("Cryptographic")

            async with session.post(
                url=api_url,
                headers=headers,
                data=cog.encrypt_cbc(
                    f'{{"class":"StarLeague",'
                    f'"method":"getWeekPlayMusic",'
                    f'"params":[{oid},"{key}"]}}',
                    iv,
                ),
            ) as r:
                ssleague = await self.read_json(r, iv)
        return ssleague

    async def read_json(
        self, response: aiohttp.ClientResponse, iv: str | bytes
    ) -> dict:
        try:
            result = await response.json(content_type=None)
        except json.JSONDecodeError:
            cog = self.bot.get_cog("Cryptographic")
            result = json.loads(cog.decrypt_cbc(await response.text(), iv))
        return result

    async def get_data(self, url: str) -> list[dict]:
        async with aiohttp.ClientSession() as session:
            async with session.get(url=url) as r:
                content = await r.read()

        cog = self.bot.get_cog("Cryptographic")
        return json.loads(
            cog.decrypt_ecb(gzip.decompress(content)).replace(rb"\/", rb"/")
        )

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
