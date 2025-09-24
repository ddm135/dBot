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
    from helpers.cryptographic import Cryptographic
    from statics.types import BasicDetails


class SuperStar(commands.Cog):
    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def get_a_json(self, basic_details: "BasicDetails") -> dict:
        headers = SuperStarHeaders()
        iv = headers["X-SuperStar-AES-IV"]

        async with aiohttp.ClientSession() as session:
            cog: "Cryptographic" = self.bot.get_cog(
                "Cryptographic"
            )  # type: ignore[assignment]

            async with session.post(
                url=basic_details["manifest"]["ServerUrl"],
                headers=headers,
                data=cog.encrypt_cbc(
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
            cog: "Cryptographic" = self.bot.get_cog(
                "Cryptographic"
            )  # type: ignore[assignment]

            async with session.post(
                url=basic_details["manifest"]["ServerUrl"],
                headers=headers,
                data=cog.encrypt_cbc(
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
            cog: "Cryptographic" = self.bot.get_cog(
                "Cryptographic"
            )  # type: ignore[assignment]

            async with session.post(
                url=basic_details["manifest"]["ServerUrl"],
                headers=headers,
                data=cog.encrypt_cbc(
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

            cog: "Cryptographic" = self.bot.get_cog(
                "Cryptographic"
            )  # type: ignore[assignment]

            async with session.post(
                url=basic_details["manifest"]["ServerUrl"],
                headers=headers,
                data=cog.encrypt_cbc(
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
            cog: "Cryptographic" = self.bot.get_cog(
                "Cryptographic"
            )  # type: ignore[assignment]

            async with session.post(
                url=basic_details["manifest"]["ServerUrl"],
                headers=headers,
                data=cog.encrypt_cbc(
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
            cog: "Cryptographic" = self.bot.get_cog(
                "Cryptographic"
            )  # type: ignore[assignment]
            result = json.loads(cog.decrypt_cbc(await response.text(), iv))
        return result

    async def get_data(self, url: str) -> list[dict]:
        async with aiohttp.ClientSession() as session:
            async with session.get(url=url) as r:
                content = await r.read()

        cog: "Cryptographic" = self.bot.get_cog(
            "Cryptographic"
        )  # type: ignore[assignment]
        return json.loads(
            cog.decrypt_ecb(gzip.decompress(content)).replace(rb"\/", rb"/")
        )

    async def get_attributes(
        self,
        game: str,
        search: Literal[
            "GroupData",
            "LocaleData",
            "MusicData",
            "ThemeData",
            "ThemeTypeData",
        ],
        item_id: int,
        attributes: dict[str, bool],
    ) -> dict:
        data_path = Path(f"data/dalcom/{game}/{search}.json")
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        found_data = {}
        for item in data:
            if item["code"] == item_id:
                for attribute in attributes:
                    found_data[attribute] = item[attribute]
                break
        else:
            for attribute in attributes:
                found_data[attribute] = None
            return found_data

        for attribute, is_file in attributes.items():
            if not is_file:
                continue

            if GAMES[game]["assetScheme"] == AssetScheme.JSON_URL:
                with open(f"data/dalcom/{game}/URLs.json", "r", encoding="utf-8") as f:
                    url_data = json.load(f)
                for url in url_data:
                    if url["code"] == found_data[attribute]:
                        found_data[attribute] = url["url"]
                        break
                else:
                    found_data[attribute] = None
            elif GAMES[game]["assetScheme"] in (
                AssetScheme.BINARY_CATALOG,
                AssetScheme.JSON_CATALOG,
            ):
                found_data[attribute] = await self.extract_file_from_bundle(
                    game, found_data[attribute]
                )

        return found_data

    async def extract_file_from_bundle(
        self,
        game: str,
        catalog_key: str,
    ) -> Path:
        catalog = self.bot.basic[game]["catalog"]
        file_path = Path(f"data/assets/{game}/{catalog_key}")
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
                        async with session.get(catalog[catalog_key]["internalId"]) as r:
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

            file_extract_paths = (
                bundle_extract_path / "Assets" / file_path.name,
                bundle_extract_path / "Assets" / "UploadFiles" / catalog_key,
                bundle_extract_path
                / "Assets"
                / "UploadFiles"
                / catalog_key.replace(",", "_"),
                bundle_extract_path / "Assets" / file_path.name.replace(",", "_"),
            )
            for file_extract_path in file_extract_paths:
                if file_extract_path.exists():
                    shutil.copyfile(file_extract_path, file_path)
                    break
            else:
                print(file_extract_paths)
                print(file_path)

        return file_path

    @staticmethod
    async def pin_new_ssl(
        embed: discord.Embed,
        pin_channel: discord.TextChannel,
        files: list[Path],
    ) -> int:
        discord_files = [discord.File(file) for file in files]
        msg = await pin_channel.send(embed=embed, files=discord_files)
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
