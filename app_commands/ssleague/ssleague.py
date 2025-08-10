# pyright: reportTypedDictNotRequiredAccess=false

import logging
from datetime import datetime
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from statics.consts import GAMES, RESET_OFFSET, AssetScheme, InfoColumns

from .autocompletes import (
    artist_autocomplete,
    song_autocomplete,
    song_id_autocomplete,
)

if TYPE_CHECKING:
    from dBot import dBot


@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
class SSLeague(commands.GroupCog, name="ssl", description="Pin SSL song of the day"):
    GAME_CHOICES = [
        app_commands.Choice(name=game_details["name"], value=game)
        for game, game_details in GAMES.items()
        if {"info"} <= set(game_details) and game_details["pinChannelIds"]
    ]

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot
        logging.getLogger(__name__).info(self.GAME_CHOICES)

    @app_commands.command()
    @app_commands.choices(game_choice=GAME_CHOICES)
    @app_commands.autocomplete(artist_choice=artist_autocomplete)
    @app_commands.autocomplete(song_name=song_autocomplete)
    @app_commands.rename(game_choice="game", artist_choice="artist", song_name="song")
    async def pin_by_name(
        self,
        itr: discord.Interaction["dBot"],
        game_choice: app_commands.Choice[str],
        artist_choice: str,
        song_name: str,
    ) -> None:
        """Pin SSL song of the day using Artist Name and Song Name

        Parameters
        -----------
        game_choice: Choice[:class:`str`]
            Game
        artist_choice: :class:`str`
            Artist Name
        song_name: :class:`str`
            Song Name
        """

        await itr.response.defer(ephemeral=True)
        if not self.bot.info_ready:
            return await itr.followup.send(
                "Song data synchronization in progress, feature unavailable.",
            )

        game = game_choice.value
        assert (guild_id := itr.guild_id)

        ssl_song = self.bot.info_by_name[game][artist_choice][song_name]
        if not ssl_song:
            return await itr.followup.send("Song not found.")

        pinned = await self.handle_ssl_command(
            game,
            ssl_song,
            guild_id,
            itr.user.name,
            artist_name=artist_choice,
            song_name=song_name,
        )

        if not pinned:
            return await itr.followup.send(
                f"Pin channel for {game_choice.name} is not set for this server.",
            )
        await itr.followup.send("Pinned!")

    @app_commands.command()
    @app_commands.choices(game_choice=GAME_CHOICES)
    @app_commands.autocomplete(song_id=song_id_autocomplete)
    @app_commands.rename(game_choice="game", song_id="id")
    async def pin_by_id(
        self,
        itr: discord.Interaction["dBot"],
        game_choice: app_commands.Choice[str],
        song_id: str,
    ) -> None:
        """Pin SSL song of the day using Song ID

        Parameters
        -----------
        game_choice: Choice[:class:`str`]
            Game
        song_id: :class:`str`
            Song ID
        """

        await itr.response.defer(ephemeral=True)
        if not self.bot.info_ready:
            return await itr.followup.send(
                "Song data synchronization in progress, feature unavailable.",
            )

        game = game_choice.value
        assert (guild_id := itr.guild_id)

        ssl_song = self.bot.info_by_id[game][song_id]
        if not ssl_song:
            return await itr.followup.send("Song not found.")

        pinned = await self.handle_ssl_command(
            game,
            ssl_song,
            guild_id,
            itr.user.name,
            song_id=int(song_id),
        )

        if not pinned:
            return await itr.followup.send(
                f"Pin channel for {game_choice.name} is not set for this server.",
            )
        await itr.followup.send("Pinned!")

    async def handle_ssl_command(
        self,
        game: str,
        ssl_song: list[str],
        guild_id: int,
        pinner: str,
        *,
        artist_name: str | None = None,
        song_name: str | None = None,
        song_id: int | None = None,
    ) -> bool:
        game_details = GAMES[game]

        pin_channel_id = game_details["pinChannelIds"].get(guild_id)
        if not pin_channel_id:
            return False
        pin_role = game_details["pinRoles"].get(guild_id)

        info_columns = game_details["info"]["columns"]
        if artist_name is None:
            artist_name = ssl_song[info_columns.index("artist_name")]
        if song_name is None:
            song_name = ssl_song[info_columns.index("song_name")]
        if song_id is None:
            song_id = int(ssl_song[info_columns.index("song_id")])

        duration = ssl_song[info_columns.index("duration")]
        skills = (
            info_columns.index("skills")
            if game_details["info"]["columns"] == InfoColumns.SSL_WITH_SKILLS.value
            else None
        )

        msd_data = self.bot.msd[game]
        url_data = self.bot.url[game]
        grd_data = self.bot.grd[game]
        for song in msd_data:
            if song["code"] == song_id:
                color = int(song["albumBgColor"][:-2], 16)
                image_url = song["album"]
                group_code = song["groupData"]
                break
        else:
            color = game_details["color"]
            image_url = None
            group_code = None

        if game_details["assetScheme"] in (
            AssetScheme.JSON_CATALOG,
            AssetScheme.BINARY_CATALOG,
        ):
            image_url = None
            group_code = None

        if game_details["assetScheme"] == AssetScheme.JSON_URL and image_url:
            for url in url_data:
                if url["code"] == image_url:
                    image_url = url["url"]
                    break

        if group_code:
            for group in grd_data:
                if group["code"] == group_code:
                    icon_url = group["emblemImage"]
                    break
            else:
                icon_url = None

            if game_details["assetScheme"] == AssetScheme.JSON_URL and icon_url:
                for url in url_data:
                    if url["code"] == icon_url:
                        icon_url = url["url"]
                        break
        else:
            icon_url = None

        timezone = game_details["timezone"]
        current_time = datetime.now(tz=timezone) - RESET_OFFSET

        artist_last_str = self.bot.ssleagues[game][artist_name]["date"]
        if artist_last_str:
            artist_last = datetime.strptime(artist_last_str, game_details["dateFormat"])
            artist_last = artist_last.replace(
                tzinfo=timezone, hour=2, minute=0, second=0, microsecond=0
            )
        else:
            artist_last = None

        song_last_str = self.bot.ssleagues[game][artist_name]["songs"][str(song_id)]
        if song_last_str:
            song_last = datetime.strptime(song_last_str, game_details["dateFormat"])
            song_last = song_last.replace(
                tzinfo=timezone, hour=2, minute=0, second=0, microsecond=0
            )
        else:
            song_last = None

        cog = self.bot.get_cog("SuperStar")
        embed = cog.SSLeagueEmbed(  # type: ignore[union-attr]
            artist_name,
            song_name,
            duration,
            image_url,
            icon_url,
            color,
            skills,
            current_time,
            pinner,
            artist_last,
            song_last,
        )

        pin_channel = self.bot.get_channel(
            pin_channel_id
        ) or await self.bot.fetch_channel(pin_channel_id)
        assert isinstance(pin_channel, discord.TextChannel)
        cog = self.bot.get_cog("SuperStar")
        new_pin = await cog.pin_new_ssl(embed, pin_channel)  # type: ignore[union-attr]
        topic = f"[{current_time.strftime("%m.%d.%y")}] {artist_name} - {song_name}"
        if pin_role:
            await pin_channel.send(f"<@&{pin_role}> {topic}")
        else:
            await pin_channel.send(topic)
        await pin_channel.edit(topic=topic)
        await cog.unpin_old_ssl(  # type: ignore[union-attr]
            embed.title,
            pin_channel,
            new_pin,
        )

        self.bot.ssleague_manual[game] = {
            "artist": artist_name,
            "song_id": str(song_id),
            "date": current_time.strftime(game_details["dateFormat"]),
        }

        return True


async def setup(bot: "dBot") -> None:
    await bot.add_cog(SSLeague(bot))
