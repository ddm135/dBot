# mypy: disable-error-code="union-attr"
# pyright: reportAttributeAccessIssue=false, reportOptionalMemberAccess=false

import gzip
import json
from typing import TYPE_CHECKING

import aiohttp
from discord.ext import commands

from statics.types import SuperStarHeaders

if TYPE_CHECKING:
    from dBot import dBot


class SuperStar(commands.Cog):
    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

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


async def setup(bot: "dBot") -> None:
    await bot.add_cog(SuperStar(bot))
