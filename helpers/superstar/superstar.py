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

    def get_period_bonuses(
        self,
        game: str,
        artists: Iterable[str],
        time: Literal["current week", "next week", "current month"] | None,
        live_theme_bonus: int = 0,
    ) -> tuple[list[BonusDict], datetime, datetime, datetime] | None:
        game_details = GAMES[game]
        bonus_data = self.bot.bonus[game]
        timezone = game_details["timezone"]
        bonus_columns = game_details["bonus"]["columns"]
        current_date = datetime.now(tz=timezone).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        match time:
            case None:
                first_date = current_date.replace(day=1, month=1)
                last_date = current_date.replace(day=31, month=12)
            case "current week":
                first_date = current_date - timedelta(days=current_date.weekday())
                last_date = first_date + timedelta(days=7)
            case "next week":
                first_date = (
                    current_date
                    - timedelta(days=current_date.weekday())
                    + timedelta(days=7)
                )
                last_date = first_date + timedelta(days=7)
            case "current month":
                first_date = current_date.replace(day=1)
                if current_date.month == 12:
                    last_date = first_date.replace(day=31)
                else:
                    last_date = current_date.replace(
                        month=current_date.month + 1, day=1
                    ) - timedelta(days=1)
            case _:
                return None
        tracking_date = first_date

        member_name_index = bonus_columns.index("member_name")
        bonus_start_index = bonus_columns.index("bonus_start")
        bonus_end_index = bonus_columns.index("bonus_end")
        bonus_amount_index = bonus_columns.index("bonus_amount")
        period_bonuses = []

        while tracking_date <= last_date:
            for artist_name in artists:
                birthday_bonuses = []
                album_bonuses = []
                last_birthday_start = None
                last_birthday_end = None
                next_birthday_start = None
                next_birthday_end = None
                for bonus in bonus_data[artist_name]:
                    start_date = bonus[bonus_start_index]
                    end_date = bonus[bonus_end_index]

                    if start_date < tracking_date and bonus[member_name_index]:
                        last_birthday_start = start_date

                    if end_date < tracking_date and bonus[member_name_index]:
                        last_birthday_end = end_date + BONUS_OFFSET

                    if (
                        not next_birthday_start
                        and tracking_date < start_date
                        and bonus[member_name_index]
                    ):
                        next_birthday_start = start_date - BONUS_OFFSET

                    if (
                        not next_birthday_end
                        and tracking_date < end_date
                        and bonus[member_name_index]
                    ):
                        next_birthday_end = end_date

                    if start_date <= tracking_date <= end_date:
                        if bonus[member_name_index]:
                            birthday_bonuses.append(bonus)
                        else:
                            album_bonuses.append(bonus)

                birthday_members = ""
                birthday_total = 0
                birthday_starts = ()
                birthday_ends = ()
                if birthday_bonuses:
                    birthday_zip = tuple(zip(*birthday_bonuses))
                    birthday_members = " + ".join(birthday_zip[member_name_index])
                    birthday_amounts = birthday_zip[bonus_amount_index]
                    for amt in birthday_amounts:
                        birthday_total += amt

                    birthday_starts = birthday_zip[bonus_start_index]
                    birthday_ends = birthday_zip[bonus_end_index]

                birthday_start = max(
                    (
                        x
                        for x in (
                            *birthday_starts,
                            last_birthday_end,
                            last_birthday_start,
                        )
                        if x
                    ),
                    default=None,
                )
                birthday_end = min(
                    (
                        x
                        for x in (
                            *birthday_ends,
                            next_birthday_end,
                            next_birthday_start,
                        )
                        if x
                    ),
                    default=None,
                )
                max_score = self.bot.artist[game][artist_name]["score"]

                if (
                    birthday_bonuses
                    and birthday_start
                    and birthday_end
                    and birthday_total > 0
                    and (
                        birthday_end == tracking_date or birthday_start == tracking_date
                    )
                ):
                    bonus_dict = BonusDict(
                        artist=artist_name,
                        members=birthday_members,
                        song=None,
                        bonusStart=birthday_start,
                        bonusEnd=birthday_end,
                        bonusAmount=birthday_total,
                        maxScore=(
                            max_score
                            + max_score * birthday_total // 100
                            + live_theme_bonus
                            if max_score
                            else 0
                        ),
                    )
                    if bonus_dict not in period_bonuses:
                        period_bonuses.append(bonus_dict)

                for bonus in album_bonuses:
                    start_date = bonus[bonus_start_index]
                    end_date = bonus[bonus_end_index]

                    song_start = max(x for x in (start_date, birthday_start) if x)
                    song_end = min(x for x in (end_date, birthday_end) if x)

                    if song_start != tracking_date and song_end != tracking_date:
                        continue

                    song_total = birthday_total + bonus[bonus_amount_index]
                    song_name = bonus[bonus_columns.index("song_name")]
                    bonus_dict = BonusDict(
                        artist=artist_name,
                        members=None,
                        song=song_name,
                        bonusStart=song_start,
                        bonusEnd=song_end,
                        bonusAmount=song_total,
                        maxScore=(
                            max_score + max_score * song_total // 100 + live_theme_bonus
                            if max_score
                            else 0
                        ),
                    )
                    if bonus_dict not in period_bonuses:
                        period_bonuses.append(bonus_dict)

            tracking_date += BONUS_OFFSET

        return period_bonuses, first_date, current_date, last_date

    class SSLeagueEmbed(_SSLeagueEmbed):
        pass


async def setup(bot: "dBot") -> None:
    await bot.add_cog(SuperStar(bot))
