# mypy: disable-error-code="assignment"
# pyright: reportAssignmentType=false, reportTypedDictNotRequiredAccess=false

import asyncio
import gzip
import json
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from zipfile import ZipFile

import aiohttp
import discord
from curl_cffi import AsyncSession
from discord.ext import commands
from google.auth.transport import requests
from google.oauth2.service_account import IDTokenCredentials

from helpers.superstar.commons import APKPURE_URL
from statics.consts import CHUNK_SIZE, GAMES, STATUS_CHANNEL, AssetScheme

from .embeds import SSLeagueEmbed as _SSLeagueEmbed
from .types import SuperStarHeaders

if TYPE_CHECKING:
    from dBot import dBot
    from helpers.cryptographic import Cryptographic


class SuperStar(commands.Cog):
    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def get_manifest(self, game: str, version: str | None = None) -> dict:
        async with aiohttp.ClientSession() as session:
            while True:
                async with session.get(
                    GAMES[game]["manifestUrl"].format(
                        version=version or self.bot.basic[game]["version"]
                    )
                ) as r:
                    manifest = await r.json(content_type=None)
                    if manifest["ActiveVersion_Android"] == version:
                        return manifest
                    version = manifest["ActiveVersion_Android"]

    async def get_a_json(self, game: str) -> dict:
        headers = SuperStarHeaders()
        iv = headers["X-SuperStar-AES-IV"]
        basic_details = self.bot.basic[game]

        async with aiohttp.ClientSession() as session:
            cog: "Cryptographic" = self.bot.get_cog("Cryptographic")

            async with session.post(
                url=basic_details["manifest"]["ServerUrl"],
                headers=headers,
                data=cog.encrypt_cbc(
                    '{"class":"Platform","method":"checkAssetBundle","params":[0]}', iv
                ),
            ) as r:
                ajs = await self.read_dalcom_json(r, iv)
        return ajs

    async def login_classic(self, game: str, credentials: dict) -> tuple[int, str]:
        headers = SuperStarHeaders()
        iv = headers["X-SuperStar-AES-IV"]
        basic_details = self.bot.basic[game]

        async with aiohttp.ClientSession() as session:
            cog: "Cryptographic" = self.bot.get_cog("Cryptographic")

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
        self, game: str, credentials: dict, target_audience: str
    ) -> tuple[int, str]:
        gredentials = IDTokenCredentials.from_service_account_file(
            filename=credentials["service_account"],
            target_audience=f"{target_audience}.apps.googleusercontent.com",
        )
        gredentials.refresh(requests.Request())
        id_token = gredentials.token

        headers = SuperStarHeaders()
        iv = headers["X-SuperStar-AES-IV"]
        basic_details = self.bot.basic[game]

        async with aiohttp.ClientSession() as session:
            cog: "Cryptographic" = self.bot.get_cog("Cryptographic")

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
        self, game: str, credentials: dict, authorization: str
    ) -> tuple[int, str]:
        headers = SuperStarHeaders()
        iv = headers["X-SuperStar-AES-IV"]
        basic_details = self.bot.basic[game]

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

            cog: "Cryptographic" = self.bot.get_cog("Cryptographic")

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

    async def get_ssleague(self, game: str, oid: int, key: str) -> dict:
        headers = SuperStarHeaders()
        iv = headers["X-SuperStar-AES-IV"]
        basic_details = self.bot.basic[game]

        async with aiohttp.ClientSession() as session:
            cog: "Cryptographic" = self.bot.get_cog("Cryptographic")

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
            cog: "Cryptographic" = self.bot.get_cog("Cryptographic")
            result = json.loads(cog.decrypt_cbc(await response.text(), iv))
        return result

    async def get_data(self, url: str) -> list[dict]:
        async with aiohttp.ClientSession() as session:
            async with session.get(url=url) as r:
                content = await r.read()

        cog: "Cryptographic" = self.bot.get_cog("Cryptographic")
        return json.loads(
            cog.decrypt_ecb(gzip.decompress(content)).replace(rb"\/", rb"/")
        )

    async def get_attributes(
        self,
        game: str,
        search: (
            Literal[
                "GroupData",
                "LocaleData",
                "MusicData",
                "ThemeData",
                "ThemeTypeData",
                "SeqData",
                "URLs",
            ]
            | tuple[list[dict], list[dict] | None]
        ),
        item_id: int,
        attributes: dict[str, bool],
    ) -> dict:
        if isinstance(search, str):
            data_path = Path(f"data/dalcom/{game}/{search}.json")
            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if GAMES[game]["assetScheme"] == AssetScheme.JSON_URL:
                with open(f"data/dalcom/{game}/URLs.json", "r", encoding="utf-8") as f:
                    url_data = json.load(f)
            else:
                url_data = None
        else:
            data = search[0]
            url_data = search[1]

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

        def find_url(attribute: str) -> str | None:
            if not url_data:
                return None

            for url in url_data:
                if url["code"] == found_data[attribute]:
                    return url["url"]
            return None

        for attribute, is_file in attributes.items():
            if not is_file:
                continue

            if url_data:
                found_data[attribute] = await asyncio.to_thread(find_url, attribute)
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
    ) -> Path | None:
        catalog = self.bot.basic[game]["catalog"]
        file_extract_path = ""
        # file_name = Path(catalog_key).name
        while dependency := catalog[catalog_key]["dependency"]:
            file_extract_path = catalog[catalog_key]["internalId"]
            catalog_key = dependency

        bundle_path = Path(f"data/files/{game}/{catalog_key}")
        bundle_extract_path = bundle_path.with_suffix("")
        bundle_extract_path.mkdir(parents=True, exist_ok=True)
        bundle_url = catalog[catalog_key]["internalId"]

        file_path = (
            bundle_extract_path / file_extract_path.replace(",", "_")
            if file_extract_path.startswith("Assets")
            # else bundle_extract_path / "Assets" / file_name.replace(",", "_")
            else bundle_extract_path / "Assets" / file_extract_path
        )

        if not file_path.exists():
            if not bundle_path.exists():
                if not bundle_url.startswith("http"):
                    xapk_path = await self.get_xapk(game)
                    if not xapk_path:
                        channel = self.bot.get_channel(
                            STATUS_CHANNEL
                        ) or await self.bot.fetch_channel(STATUS_CHANNEL)
                        assert isinstance(channel, discord.TextChannel)
                        await channel.send(
                            f"<@{self.bot.owner_id}> Built-in bundle: `{bundle_url}`"
                        )
                        return None

                    apk_bundle_path = catalog[catalog_key]["internalId"].split(
                        "/Android/"
                    )[-1]
                    with ZipFile(xapk_path, "r") as xapk:
                        with xapk.open("base_assets.apk", "r") as base_assets:
                            with ZipFile(base_assets, "r") as apk:
                                with apk.open(
                                    f"assets/aa/Android/{apk_bundle_path}", "r"
                                ) as bundle_file:
                                    with open(bundle_path, "wb") as f:
                                        f.write(bundle_file.read())
                else:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(bundle_url) as r:
                            with open(bundle_path, "wb") as f:
                                async for chunk in r.content.iter_chunked(CHUNK_SIZE):
                                    f.write(chunk)

            process = await asyncio.create_subprocess_exec(
                "utils/bundle",
                str(bundle_path),
                str(bundle_extract_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            bundle_path.unlink(missing_ok=True)

        return file_path

    async def get_xapk(self, game) -> Path | None:
        xapk_folder_path = Path(f"data/xapks/{game}")
        xapk_folder_path.mkdir(parents=True, exist_ok=True)
        xapks = list(
            xapk_folder_path.rglob(f"*{self.bot.basic[game]["version"]}*.xapk")
        )
        if xapks:
            xapk_path = xapks[0]
            if not zipfile.is_zipfile(xapk_path):
                xapk_path.unlink(missing_ok=True)
            else:
                return xapk_path

        for file in xapk_folder_path.iterdir():
            if file.is_file():
                file.unlink()
        async with AsyncSession() as session:
            response = await session.get(
                APKPURE_URL.format(package_name=GAMES[game]["packageName"]),
                impersonate="chrome",
                allow_redirects=False,
            )
            xapk_url = response.headers.get("Location")
            if not xapk_url:
                return None

        async with aiohttp.ClientSession() as session:
            async with session.get(xapk_url) as r:
                disposition = r.headers.get("Content-Disposition")
                if not disposition:
                    return None

                xapk_file_name = disposition.split("filename=")[-1].strip('"')
                # if self.bot.basic[game]["version"] not in xapk_file_name:
                #     return None

                xapk_path = xapk_folder_path / xapk_file_name
                with open(xapk_path, "wb") as f:
                    async for chunk in r.content.iter_chunked(CHUNK_SIZE):
                        f.write(chunk)

        return xapk_path

    @staticmethod
    async def pin_new_ssl(
        embed: discord.Embed,
        pin_channel: discord.TextChannel,
        files: list[discord.File],
    ) -> int:
        msg = await pin_channel.send(embed=embed, files=files)
        await asyncio.sleep(1)
        await msg.pin()
        return msg.id

    async def unpin_old_ssl(
        self, embed: discord.Embed, pin_channel: discord.TextChannel, new_pin: int
    ) -> None:
        if embed.title and "SSL #" in embed.title:
            embed_title = embed.title
        elif embed.author.name and "SSL #" in embed.author.name:
            embed_title = embed.author.name.rpartition(" - ")[2]
        else:
            return

        pins = await pin_channel.pins()
        for pin in pins:
            if pin.id == new_pin or self.bot.user and pin.author.id != self.bot.user.id:
                continue

            embeds = pin.embeds
            if embeds and (
                embeds[0].title
                and embed_title in embeds[0].title
                or embeds[0].author.name
                and embed_title in embeds[0].author.name
            ):
                await pin.unpin()
                break

    class SSLeagueEmbed(_SSLeagueEmbed):
        pass


async def setup(bot: "dBot") -> None:
    await bot.add_cog(SuperStar(bot))
