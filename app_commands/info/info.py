# pyright: reportTypedDictNotRequiredAccess=false

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from statics.consts import GAMES, InfoColumns

from .autocompletes import artist_autocomplete, song_autocomplete
from .embeds import InfoDetailsEmbed, InfoEmbed
from .views import InfoView

if TYPE_CHECKING:
    from dBot import dBot
    from helpers.superstar import SuperStar


class Info(commands.Cog):
    GAME_CHOICES = [
        app_commands.Choice(name=game_details["name"], value=game)
        for game, game_details in GAMES.items()
        if {"info"} <= set(game_details)
    ]

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    @app_commands.command()
    @app_commands.choices(game_choice=GAME_CHOICES)
    @app_commands.autocomplete(artist_name=artist_autocomplete)
    @app_commands.autocomplete(song_name=song_autocomplete)
    @app_commands.rename(game_choice="game", artist_name="artist")
    async def info(
        self,
        itr: discord.Interaction["dBot"],
        game_choice: app_commands.Choice[str],
        artist_name: str | None = None,
        song_name: str | None = None,
    ) -> None:
        """View song information, sorted by duration

        Parameters
        -----------
        game_choice: Choice[:class:`str`]
            Game
        artist_name: Optional[:class:`str`]
            Artist Name
        song_name: Optional[:class:`str`]
            Song Name
        """

        await itr.response.defer()
        game_details = GAMES[game_choice.value]
        info_columns = game_details["info"]["columns"]
        song_id_index = info_columns.index("song_id")

        icon: str | Path | None
        if not artist_name:
            songs = self.bot.info_by_id[game_choice.value].values()
            icon = self.bot.basic[game_choice.value]["iconUrl"]
        else:
            if not (
                songs := (
                    self.bot.info_by_name[game_choice.value]
                    .get(artist_name, {})
                    .values()
                )
            ):
                return await itr.followup.send("Artist not found.")
            icon = self.bot.emblem[game_choice.value][artist_name]

            if song_name:
                if not (
                    song := self.bot.info_by_name[game_choice.value]
                    .get(artist_name, {})
                    .get(song_name)
                ):
                    return await itr.followup.send("Song not found.")

                cog: "SuperStar" = self.bot.get_cog(
                    "SuperStar",
                )  # type: ignore[assignment]
                song_id = song[song_id_index]
                results = await cog.get_attributes(
                    game_choice.value,
                    "MusicData",
                    int(song_id),
                    {"albumBgColor": False, "album": True},
                )
                color = (
                    int(results["albumBgColor"][:-2], 16)
                    if results["albumBgColor"]
                    else game_details["color"]
                )
                album = results["album"]

                album_info: list[str] | dict[str, str]
                if "bonus" in game_details:
                    album_info = next(
                        bonus
                        for bonus in self.bot.bonus[game_choice.value][artist_name]
                        if song_id
                        == bonus[
                            GAMES[game_choice.value]["bonus"]["columns"].index(
                                "song_id"
                            )
                        ]
                    )
                    results = await cog.get_attributes(
                        game_choice.value,
                        "MusicData",
                        int(song_id),
                        {
                            "myrecordQualifyingScore": False,
                        },
                    )
                else:
                    results = await cog.get_attributes(
                        game_choice.value,
                        "MusicData",
                        int(song_id),
                        {
                            "albumName": False,
                            "releaseDate": False,
                            "myrecordQualifyingScore": False,
                        },
                    )
                    album_info = {
                        "album_name": (
                            await cog.get_attributes(
                                game_choice.value,
                                "LocaleData",
                                results["albumName"],
                                {"enUS": False},
                            )
                        )["enUS"],
                        "bonus_date": datetime.fromtimestamp(
                            results["releaseDate"] / 1000, tz=game_details["timezone"]
                        ).strftime(game_details["dateFormat"]),
                    }
                return await itr.followup.send(
                    embed=InfoDetailsEmbed(
                        game_choice.value,
                        artist_name,
                        song_name,
                        self.bot.info_from_file[game_choice.value][song[song_id_index]][
                            "sound"
                        ]["duration"],
                        self.bot.info_from_file[game_choice.value][song[song_id_index]][
                            "seq"
                        ],
                        album,
                        icon,
                        color,
                        album_info,
                        (
                            song[info_columns.index("skills")]
                            if info_columns == InfoColumns.SSL_WITH_SKILLS.value
                            else None
                        ),
                        results["myrecordQualifyingScore"],
                    ),
                    files=[
                        discord.File(file)
                        for file in (album, icon)
                        if isinstance(file, Path)
                    ],
                )

        sorted_songs = sorted(
            songs,
            key=lambda x: self.bot.info_from_file[game_choice.value][x[song_id_index]][
                "sound"
            ]["duration"],
        )
        msg = await itr.followup.send(
            embed=InfoEmbed(
                game_choice.value,
                artist_name,
                sorted_songs,
                self.bot.info_from_file[game_choice.value],
                icon,
            ),
            files=[discord.File(icon)] if isinstance(icon, Path) else [],
            wait=True,
        )
        view = InfoView(
            msg,
            game_choice.value,
            artist_name,
            sorted_songs,
            self.bot.info_from_file[game_choice.value],
            itr.user,
            icon,
        )
        await msg.edit(view=view)


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Info(bot))
