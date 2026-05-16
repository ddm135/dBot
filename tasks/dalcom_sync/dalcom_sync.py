# mypy: disable-error-code="assignment, import-untyped"
# pyright: reportAssignmentType=false, reportTypedDictNotRequiredAccess=false

import binascii
import json
import logging
import math
import re
import shutil
from collections import defaultdict
from datetime import datetime, time
from pathlib import Path
from typing import TYPE_CHECKING

import aiohttp
import discord
import soundfile
from discord.ext import commands, tasks
from googleapiclient.http import MediaFileUpload

from statics.consts import GAMES, TIMEZONES

from .commons import BORDER_CHANNEL, BORDER_FOLDER, FOLDER_MIME
from .types import Seq

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3 import File

    from dBot import dBot
    from helpers.google_drive import GoogleDrive
    from helpers.google_sheets import GoogleSheets
    from helpers.superstar import SuperStar


class DalcomSync(commands.Cog):
    LOGGER = logging.getLogger(__name__.rpartition(".")[0])

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await self.dalcom_sync()
        self.dalcom_sync.start()

    async def cog_unload(self) -> None:
        self.dalcom_sync.cancel()

    @tasks.loop(time=[time(hour=h, minute=15) for h in range(24)])
    async def dalcom_sync(self) -> None:
        drive_cog: "GoogleDrive" = self.bot.get_cog("GoogleDrive")
        sheets_cog: "GoogleSheets" = self.bot.get_cog("GoogleSheets")
        ss_cog: "SuperStar" = self.bot.get_cog("SuperStar")
        border_channel = self.bot.get_channel(
            BORDER_CHANNEL
        ) or await self.bot.fetch_channel(BORDER_CHANNEL)
        assert isinstance(border_channel, discord.TextChannel)
        drive_folders = await drive_cog.get_file_list(
            BORDER_FOLDER, mime_type=FOLDER_MIME
        )

        for game, game_details in GAMES.items():
            self.LOGGER.info("Downloading Dalcom data: %s...", game_details["name"])

            bundle_folders: set[Path] = set()
            missing_music = []
            borders = {}

            music_info_file = Path(f"data/MusicData/{game}.json")
            if not self.bot.info_from_file.get(game):
                if music_info_file.exists():
                    with open(music_info_file, "r", encoding="utf-8") as f:
                        self.bot.info_from_file[game] = json.load(f)
                else:
                    self.bot.info_from_file[game] = {}

            if "catalogPattern" in game_details:
                artist_name_index = game_details["spreadsheet"]["columns"][0].index(
                    "artist_name"
                )
                artist = {}
                for song in self.bot.info_by_id[game].values():
                    artist_name = song[artist_name_index]
                    if artist_name in artist:
                        continue

                    artist[artist_name] = {
                        "code": None,
                        "emblem": None,
                        "count": 0,
                        "score": 0,
                    }

                self.bot.artist[game] = artist
                self.bot.live_theme[game]["max"] = 0

                for k, v in self.bot.basic[game]["catalog"].items():
                    if match := re.fullmatch(game_details["catalogPattern"]["seq"], k):
                        song_id = match.group(1)
                        difficulty = match.group(2).capitalize()
                        dependency = (
                            self.bot.info_from_file[game]
                            .setdefault(song_id, {})
                            .setdefault("seq", {})
                            .setdefault(difficulty, {})
                            .get("dependency")
                        )
                        if (
                            song_id in self.bot.info_from_file[game]
                            and difficulty
                            in self.bot.info_from_file[game][song_id].get("seq", {})
                            and dependency == v["dependency"]
                        ):
                            continue

                        src_path = await ss_cog.extract_file_from_bundle(game, k)
                        if not src_path:
                            continue
                        dst_path = Path(
                            f"data/MusicData/{game}/{song_id}_{difficulty}.seq"
                        )
                        await self.copy_file(src_path, dst_path, bundle_folders)

                        seq_obj = Seq(dst_path)
                        self.bot.info_from_file[game][song_id]["seq"][difficulty] = {
                            "count": seq_obj.count,
                            "duration": seq_obj.SEQData_Info["secLength"],
                            "key": k,
                            "dependency": v["dependency"],
                        }

                        if song_id not in self.bot.info_by_id[game]:
                            missing_music.append(
                                [
                                    song_id,
                                    str(seq_obj.SEQData_Object),
                                ]
                            )
                    elif match := re.fullmatch(
                        game_details["catalogPattern"]["border"], k
                    ):
                        border_id = match.group(1)
                        border_internal = Path(v["internalId"])
                        border_name = f"{border_id}{border_internal.suffix}"
                        borders[border_name] = k

                for song_id in self.bot.info_from_file[game]:
                    if "duration" in self.bot.info_from_file[game][song_id]:
                        continue

                    duration = min(
                        self.bot.info_from_file[game][song_id]["seq"][difficulty][
                            "duration"
                        ]
                        for difficulty in self.bot.info_from_file[game][song_id]["seq"]
                    )
                    duration = math.floor(duration + 0.5)
                    minutes = duration // 60
                    seconds = str(duration % 60).zfill(2)
                    self.bot.info_from_file[game][song_id][
                        "duration"
                    ] = f"{minutes}:{seconds}"

                with open(music_info_file, "w", encoding="utf-8") as f:
                    json.dump(self.bot.info_from_file[game], f, indent=4)

                for path in bundle_folders:
                    shutil.rmtree(path)

                missing_music.append(["-", "-"])
                await sheets_cog.update_sheet_data(
                    game_details["spreadsheet"]["id"],
                    game_details["spreadsheet"]["ranges"][0].partition("!")[0]
                    + "!Y2:Z",
                    missing_music,
                )

                for folder in drive_folders["files"]:
                    if folder["name"] == game_details["name"]:
                        border_folder = folder["id"]
                        break
                else:
                    metadata: "File" = {
                        "name": game_details["name"],
                        "mimeType": FOLDER_MIME,
                        "parents": [BORDER_FOLDER],
                    }
                    border_folder = (await drive_cog.create_file(metadata))[0]

                next_page = ""
                while True:
                    border_files = await drive_cog.get_file_list(
                        border_folder, next_page=next_page
                    )
                    for file in border_files["files"]:
                        borders.pop(file["name"], None)
                    if not (next_page := border_files.get("nextPageToken", "")):
                        break

                if borders:
                    self.LOGGER.info("Uploading borders: %s...", game_details["name"])
                    for border_name, border_key in borders.items():
                        border_file_path = await ss_cog.extract_file_from_bundle(
                            game, border_key
                        )
                        if not border_file_path:
                            continue

                        border_media = None
                        for path in border_file_path.parent.iterdir():
                            if not path.is_file():
                                continue

                            with open(path, "rb") as f:
                                header = f.read(8)
                                if header == b"\x89PNG\r\n\x1a\n":
                                    border_media = MediaFileUpload(path)
                                    break
                        if not border_media:
                            continue

                        metadata = {"name": border_name, "parents": [border_folder]}
                        link = (await drive_cog.create_file(metadata, border_media))[2]
                        await border_channel.send(
                            f"{game_details["name"]}: "
                            f"{border_name.replace(r"<", r"\<")}\n<{link}>"
                        )

                continue

            try:
                ajs_path = Path(f"data/dalcom/{game}/a.json")
                if ajs_path.exists():
                    with open(ajs_path, "r", encoding="utf-8-sig") as f:
                        stored_ajs = json.load(f)
                else:
                    stored_ajs = defaultdict(lambda: defaultdict(dict))

                if "iconUrl" in game_details:
                    ajs = {"code": 1000, "result": stored_ajs}
                    stored_ajs = ajs
                else:
                    ajs = await ss_cog.get_a_json(game)

                refresh = False
                if ajs["code"] != 1000:
                    ajs = stored_ajs
                elif (
                    not stored_ajs
                    or ajs["result"]["version"] != stored_ajs["result"]["version"]
                ):
                    refresh = True
                if not ajs:
                    continue

                data_files = [
                    "ArtistData",
                    "GroupData",
                    "HiddenGameData",
                    "LiveThemeData",
                    "LocaleData",
                    "MusicData",
                    "ThemeData",
                    "SeqData",
                    "ThemeTypeData",
                    "URLs",
                    "WorldRecordData",
                ]

                dalcom_data = {}
                for data_file in data_files:
                    if data_file not in ajs["result"]["context"]:
                        continue

                    data_path = Path(f"data/dalcom/{game}/{data_file}.json")
                    if (
                        not stored_ajs
                        or data_file not in stored_ajs["result"]["context"]
                        or ajs["result"]["context"][data_file]["version"]
                        != stored_ajs["result"]["context"][data_file]["version"]
                        or refresh
                        or not data_path.exists()
                    ):
                        data = await ss_cog.get_data(
                            ajs["result"]["context"][data_file]["file"]
                        )
                        data_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(data_path, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=4)
                    else:
                        with open(data_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if isinstance(data, list):
                            new_data = {str(item["code"]): item for item in data}
                            with open(data_path, "w", encoding="utf-8") as f:
                                json.dump(new_data, f, indent=4)
                            data = new_data
                    dalcom_data[data_file] = data

                if refresh:
                    ajs_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(ajs_path, "w", encoding="utf-8") as f:
                        json.dump(ajs, f, indent=4)

                # Check if game has Live Theme Collection Reward
                max_live = None
                if "LiveThemeData" in dalcom_data and "collectRewardID" in next(
                    iter(dalcom_data["LiveThemeData"].values())
                ):
                    max_live = 0

                artist_name_index = game_details["spreadsheet"]["columns"][0].index(
                    "artist_name"
                )
                artist = {}
                for song_id, song in self.bot.info_by_id[game].items():
                    artist_name = song[artist_name_index]
                    if artist_name in artist:
                        continue

                    # Find artist code using song ID
                    int_song_id = int(song_id)
                    results = await ss_cog.get_attributes(
                        game,
                        (dalcom_data["MusicData"], dalcom_data.get("URLs")),
                        [int_song_id],
                        {"groupData": False},
                    )
                    artist_code = results[int_song_id]["groupData"]

                    # Get artist emblem
                    results = await ss_cog.get_attributes(
                        game,
                        (dalcom_data["GroupData"], dalcom_data.get("URLs")),
                        [artist_code],
                        {"emblemImage": True},
                    )
                    emblem = results[artist_code]["emblemImage"]

                    # Count members
                    member_count = 0
                    for member in dalcom_data["ArtistData"].values():
                        if (
                            member["group"] == artist_code
                            and member.get("artistType", 1) != 4
                        ):
                            member_count += 1

                    # Calculate base max score
                    max_score = (
                        game_details["base_score"] + 15_000 * (member_count - 3)
                        if "base_score" in game_details
                        else 0
                    )

                    artist[artist_name] = {
                        "code": artist_code,
                        "emblem": emblem,
                        "count": member_count,
                        "score": max_score,
                    }

                    if max_live is not None:
                        for theme in dalcom_data["LiveThemeData"].values():
                            if theme["groupID"] == artist_code:
                                max_live += 15_000 * member_count

                self.bot.artist[game] = artist
                self.bot.live_theme[game]["max"] = max_live if max_live else 0

                for seq in dalcom_data.get("SeqData", {}).values():
                    linked_music = str(seq["linkedMusic"])
                    seq_level = str(seq["seqLevel"])
                    current_key = (
                        self.bot.info_from_file[game]
                        .setdefault(linked_music, {})
                        .setdefault("seq", {})
                        .setdefault(seq_level, {})
                        .get("key")
                    )
                    dependency = (
                        self.bot.info_from_file[game]
                        .setdefault(linked_music, {})
                        .setdefault("seq", {})
                        .setdefault(seq_level, {})
                        .get("dependency")
                    )
                    found_key = seq["seqPath"]
                    if isinstance(found_key, int):
                        results = await ss_cog.get_attributes(
                            game,
                            (dalcom_data["URLs"], None),
                            [found_key],
                            {"url": False},
                        )
                        found_key = results[found_key]["url"]
                    found_dependency = (
                        self.bot.basic[game]
                        .get("catalog", {})
                        .get(found_key, {})
                        .get("dependency")
                    )

                    if (
                        linked_music in self.bot.info_from_file[game]
                        and seq_level
                        in self.bot.info_from_file[game][linked_music].get("seq", {})
                        and current_key == found_key
                        and dependency == found_dependency
                    ):
                        continue

                    results = await ss_cog.get_attributes(
                        game,
                        (dalcom_data["SeqData"], dalcom_data.get("URLs")),
                        [seq["code"]],
                        {"seqPath": True},
                    )
                    src_path = results[seq["code"]]["seqPath"]
                    if not src_path:
                        continue
                    dst_path = Path(
                        f"data/MusicData/{game}"
                        f"/{seq["linkedMusic"]}_{seq["seqLevel"]}.seq"
                    )
                    await self.copy_file(src_path, dst_path, bundle_folders)

                    seq_obj = Seq(dst_path)
                    self.bot.info_from_file[game][linked_music]["seq"][seq_level] = {
                        "count": seq_obj.count,
                        "duration": seq_obj.SEQData_Info["secLength"],
                        "key": found_key,
                        "dependency": found_dependency,
                    }

                for music in dalcom_data["MusicData"].values():
                    music_code = str(music["code"])
                    music_results = await ss_cog.get_attributes(
                        game,
                        (dalcom_data["MusicData"], dalcom_data.get("URLs")),
                        [music["code"]],
                        {"localeName": False, "isHidden": False},
                    )

                    if music_results[music["code"]]["isHidden"]:
                        current_key = (
                            self.bot.info_from_file[game]
                            .setdefault(music_code, {})
                            .setdefault("sound", {})
                            .get("key")
                        )
                        dependency = (
                            self.bot.info_from_file[game]
                            .setdefault(music_code, {})
                            .setdefault("sound", {})
                            .get("dependency")
                        )
                        found_key = music["sound"]
                        if isinstance(found_key, int):
                            results = await ss_cog.get_attributes(
                                game,
                                (dalcom_data["URLs"], None),
                                [found_key],
                                {"url": False},
                            )
                            found_key = results[found_key]["url"]
                        found_dependency = (
                            self.bot.basic[game]
                            .get("catalog", {})
                            .get(found_key, {})
                            .get("dependency")
                        )

                        if not (
                            music_code in self.bot.info_from_file[game]
                            and current_key == found_key
                            and dependency == found_dependency
                        ):
                            results = await ss_cog.get_attributes(
                                game,
                                (dalcom_data["MusicData"], dalcom_data.get("URLs")),
                                [music["code"]],
                                {"sound": True},
                            )
                            src_path = results[music["code"]]["sound"]
                            if not src_path:
                                continue
                            dst_path = Path(
                                f"data/MusicData/{game}/{music["code"]}.ogg"
                            )
                            await self.copy_file(src_path, dst_path, bundle_folders)

                            duration = int(soundfile.info(dst_path).duration)
                            minutes = duration // 60
                            seconds = str(duration % 60).zfill(2)
                            self.bot.info_from_file[game][music_code]["sound"] = {
                                "duration": f"{minutes}:{seconds}",
                                "key": found_key,
                                "dependency": found_dependency,
                            }

                    if music_code not in self.bot.info_by_id[game]:
                        locale_results = await ss_cog.get_attributes(
                            game,
                            (dalcom_data["LocaleData"], dalcom_data.get("URLs")),
                            [music_results[music["code"]]["localeName"]],
                            {"koKR": False, "enUS": False, "jaJP": False},
                        )
                        missing_music.append(
                            [
                                music_code,
                                locale_results[
                                    music_results[music["code"]]["localeName"]
                                ]["koKR"],
                                locale_results[
                                    music_results[music["code"]]["localeName"]
                                ]["enUS"],
                                locale_results[
                                    music_results[music["code"]]["localeName"]
                                ]["jaJP"],
                                music_results[music["code"]]["isHidden"],
                            ]
                        )

                    if "SeqData" in dalcom_data:
                        seqs = {}
                    else:
                        seqs = {
                            "seqEasy": "_4.seq",
                            "seqNormal": "_7.seq",
                            "seqHard": "_13.seq",
                        }

                    for difficulty, extension in seqs.items():
                        current_key = (
                            self.bot.info_from_file[game]
                            .setdefault(music_code, {})
                            .setdefault("seq", {})
                            .setdefault(difficulty.replace("seq", ""), {})
                            .get("key")
                        )
                        dependency = (
                            self.bot.info_from_file[game]
                            .setdefault(music_code, {})
                            .setdefault("seq", {})
                            .setdefault(difficulty.replace("seq", ""), {})
                            .get("dependency")
                        )
                        found_key = music[difficulty]
                        if isinstance(found_key, int):
                            results = await ss_cog.get_attributes(
                                game,
                                (dalcom_data["URLs"], None),
                                [found_key],
                                {"url": False},
                            )
                            found_key = results[found_key]["url"]
                        found_dependency = (
                            self.bot.basic[game]
                            .get("catalog", {})
                            .get(found_key, {})
                            .get("dependency")
                        )

                        if (
                            music_code in self.bot.info_from_file[game]
                            and difficulty.replace("seq", "")
                            in self.bot.info_from_file[game][music_code].get("seq", {})
                            and current_key == found_key
                            and dependency == found_dependency
                        ):
                            continue

                        results = await ss_cog.get_attributes(
                            game,
                            (dalcom_data["MusicData"], dalcom_data.get("URLs")),
                            [music["code"]],
                            {difficulty: True},
                        )
                        src_path = results[music["code"]][difficulty]
                        if not src_path:
                            continue
                        dst_path = Path(
                            f"data/MusicData/{game}/{music['code']}{extension}"
                        )
                        await self.copy_file(src_path, dst_path, bundle_folders)

                        seq_obj = Seq(dst_path)
                        self.bot.info_from_file[game][music_code]["seq"][
                            difficulty.replace("seq", "")
                        ] = {
                            "count": seq_obj.count,
                            "duration": seq_obj.SEQData_Info["secLength"],
                            "key": found_key,
                            "dependency": found_dependency,
                        }

                    duration = min(
                        self.bot.info_from_file[game][music_code]["seq"][difficulty][
                            "duration"
                        ]
                        for difficulty in self.bot.info_from_file[game][music_code][
                            "seq"
                        ]
                    )
                    duration = math.floor(duration + 0.5)
                    minutes = duration // 60
                    seconds = str(duration % 60).zfill(2)
                    self.bot.info_from_file[game][music_code][
                        "duration"
                    ] = f"{minutes}:{seconds}"

                missing_music.append(["-", "-", "-", "-", "-"])
                await sheets_cog.update_sheet_data(
                    game_details["spreadsheet"]["id"],
                    game_details["spreadsheet"]["ranges"][0].partition("!")[0]
                    + "!V2:Z",
                    missing_music,
                )

                with open(music_info_file, "w", encoding="utf-8") as f:
                    json.dump(self.bot.info_from_file[game], f, indent=4)

                for path in bundle_folders:
                    shutil.rmtree(path)

                # Get World Record seasons and duration
                current_date = datetime.now(tz=TIMEZONES[game_details["timezone"]])
                if (
                    "firstSeason" not in game_details
                    and "catalogPattern" not in game_details
                ):
                    for reward in dalcom_data["WorldRecordData"].values():
                        season_code = reward["seasonCode"]
                        if season_code in self.bot.world_record.setdefault(game, {}):
                            continue

                        start_date = datetime.fromtimestamp(
                            reward["startAt"] / 1000,
                            tz=TIMEZONES[game_details["timezone"]],
                        )
                        if start_date > current_date:
                            continue
                        end_date = datetime.fromtimestamp(
                            reward["endAt"] / 1000,
                            tz=TIMEZONES[game_details["timezone"]],
                        )
                        self.bot.world_record[game][season_code] = {
                            "start": start_date,
                            "end": end_date,
                        }

                if "catalogUrl" not in game_details:
                    continue

                for border in dalcom_data["ThemeTypeData"].values():
                    if not border["code"]:
                        continue

                    suffixes = {"_Large": ""}
                    for theme in dalcom_data["ThemeData"].values():
                        if theme["themeTypeCode"] == border["code"]:
                            if theme["nameImageZoom"]:
                                suffixes["_Zoom"] = "z"
                            break
                    else:
                        continue

                    if not theme["limitedType"]:
                        continue

                    results = await ss_cog.get_attributes(
                        game,
                        (dalcom_data["LocaleData"], None),
                        [theme["localeName"]],
                        {"enUS": False},
                    )
                    name = results[theme["localeName"]]["enUS"]
                    if not name:
                        continue

                    catalog_key = Path(border["gradeR"])
                    for k, v in suffixes.items():
                        border_name = (
                            f"{border["code"]}{v} - {name}{catalog_key.suffix}"
                        )
                        borders[border_name] = str(
                            catalog_key.with_stem(catalog_key.stem + k)
                        )

                for folder in drive_folders["files"]:
                    if folder["name"] == game_details["name"]:
                        border_folder = folder["id"]
                        break
                else:
                    metadata = {
                        "name": game_details["name"],
                        "mimeType": FOLDER_MIME,
                        "parents": [BORDER_FOLDER],
                    }
                    border_folder = (await drive_cog.create_file(metadata))[0]

                next_page = ""
                while True:
                    border_files = await drive_cog.get_file_list(
                        border_folder, next_page=next_page
                    )
                    for file in border_files["files"]:
                        borders.pop(file["name"], None)
                    if not (next_page := border_files.get("nextPageToken", "")):
                        break

                if borders:
                    self.LOGGER.info("Uploading borders: %s...", game_details["name"])
                    for border_name, border_key in borders.items():
                        try:
                            border_file_path = await ss_cog.extract_file_from_bundle(
                                game, border_key
                            )
                            if not border_file_path:
                                continue
                            border_media = MediaFileUpload(border_file_path)
                        except KeyError:
                            continue
                        metadata = {"name": border_name, "parents": [border_folder]}
                        link = (await drive_cog.create_file(metadata, border_media))[2]
                        await border_channel.send(
                            f"{game_details["name"]}: "
                            f"{border_name.replace(r"<", r"\<")}\n<{link}>"
                        )

            except (json.JSONDecodeError, binascii.Error, ValueError):
                self.LOGGER.info(
                    "%s server is unavailable. Skipping...", game_details["name"]
                )
                continue
            except Exception as e:
                self.LOGGER.exception(str(e))
                continue

    @staticmethod
    async def copy_file(src: str | Path, dst: Path, bundle_folders: set[Path]):
        dst.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(src, Path):
            shutil.copyfile(src, dst)
            while not src.is_dir() or src.name != "Assets":
                src = src.parent
            src = src.parent
            bundle_folders.add(src)
        else:
            async with aiohttp.ClientSession() as session:
                async with session.get(src) as r:
                    with open(dst, "wb") as f:
                        f.write(await r.read())


async def setup(bot: "dBot") -> None:
    await bot.add_cog(DalcomSync(bot))
