import asyncio
import gzip
import json
from datetime import datetime, timedelta
from typing import Optional, Union
from zoneinfo import ZoneInfo

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from app_commands.autocomplete.ssLeague import (
    _ssl_preprocess,
    artist_autocomplete,
    song_autocomplete,
    song_id_autocomplete,
)
from static.dConsts import (
    A_JSON_BODY,
    A_JSON_HEADERS,
    GAMES,
    OK_ROLE_OWNER,
    SSRG_ROLE_MOD,
    SSRG_ROLE_SS,
)
from static.dHelpers import decrypt_cbc, decrypt_ecb


class SSLeague(commands.GroupCog, name="ssl"):
    GAME_CHOICES = [
        app_commands.Choice(name=game["name"], value=key)
        for key, game in GAMES.items()
        if game["pinChannelIds"]
    ]

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        description="Pin SSL song of the day using Artist Name and Song Name"
    )
    @app_commands.choices(game=GAME_CHOICES)
    @app_commands.autocomplete(artist_name=artist_autocomplete)
    @app_commands.autocomplete(song_name=song_autocomplete)
    @app_commands.checks.has_any_role(OK_ROLE_OWNER, SSRG_ROLE_MOD, SSRG_ROLE_SS)
    async def pin_by_name(
        self,
        itr: discord.Interaction,
        game: app_commands.Choice[str],
        artist_name: str,
        song_name: str,
    ):
        await itr.response.defer(ephemeral=True)
        (
            game_details,
            ssl_data,
            artist_name_index,
            song_name_index,
            song_id_index,
            duration_index,
            image_url_index,
            skills_index,
        ) = _ssl_preprocess(game.value)

        try:
            song = next(
                s
                for s in ssl_data
                if s[artist_name_index].lower() == artist_name.lower()
                and s[song_name_index].lower() == song_name.lower()
            )

            timezone = game_details["timezone"]
            assert (offset := game_details["sslOffset"])
            assert (pin_channel_ids := game_details["pinChannelIds"])
            assert itr.guild_id
            api_url = game_details["api"]

            await self._handle_ssl_command(
                itr,
                song[artist_name_index],
                song[song_name_index],
                int(song[song_id_index]),
                song[duration_index],
                song[image_url_index],
                song[skills_index] if skills_index else None,
                timezone,
                offset,
                pin_channel_ids[itr.guild_id],
                api_url,
            )
        except StopIteration:
            await itr.followup.send("Song not found")

    @app_commands.command(description="Pin SSL song of the day using Song ID")
    @app_commands.choices(game=GAME_CHOICES)
    @app_commands.autocomplete(song_id=song_id_autocomplete)
    @app_commands.checks.has_any_role(OK_ROLE_OWNER, SSRG_ROLE_MOD, SSRG_ROLE_SS)
    async def pin_by_id(
        self,
        itr: discord.Interaction,
        game: app_commands.Choice[str],
        song_id: str,
    ):
        await itr.response.defer(ephemeral=True)
        (
            game_details,
            ssl_data,
            artist_name_index,
            song_name_index,
            song_id_index,
            duration_index,
            image_url_index,
            skills_index,
        ) = _ssl_preprocess(game.value)

        try:
            song = next(s for s in ssl_data if s[song_id_index] == song_id)

            timezone = game_details["timezone"]
            assert (offset := game_details["sslOffset"])
            assert (pin_channel_ids := game_details["pinChannelIds"])
            assert itr.guild_id
            api_url = game_details["api"]

            await self._handle_ssl_command(
                itr,
                song[artist_name_index],
                song[song_name_index],
                int(song[song_id_index]),
                song[duration_index],
                song[image_url_index],
                song[skills_index] if skills_index else None,
                timezone,
                offset,
                pin_channel_ids[itr.guild_id],
                api_url,
            )
        except StopIteration:
            await itr.followup.send("Song not found")

    async def _handle_ssl_command(
        self,
        itr: discord.Interaction,
        artist_name: str,
        song_name: str,
        song_id: int,
        duration: str,
        image_url: str,
        skills: Optional[str],
        timezone: ZoneInfo,
        offset: timedelta,
        pin_channel_id: int,
        api_url: str,
    ) -> None:
        color = await self._get_song_color(song_id, api_url)

        current_time = datetime.now(timezone) - offset
        embed, embed_title = self._generate_embed(
            artist_name, song_name, duration, image_url, current_time, color, skills
        )

        pin_channel = self.bot.get_channel(pin_channel_id)

        try:
            assert isinstance(pin_channel, discord.TextChannel)
            await self._unpin_old_ssl(embed_title, pin_channel)
            await self._pin_new_ssl(itr, embed, pin_channel)
            await pin_channel.edit(
                topic=(
                    f"[{current_time.strftime("%m.%d.%y")}] "
                    f"{artist_name} - {song_name}"
                )
            )
        except AssertionError:
            await itr.followup.send("Bot is not in server")

    async def _get_a_json(self, api_url: str) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url=api_url,
                headers=A_JSON_HEADERS,
                data=A_JSON_BODY,
            ) as r:
                try:
                    ajs = await r.json(content_type=None)
                except json.JSONDecodeError:
                    ajs = json.loads(decrypt_cbc(await r.text()))
        return ajs

    async def _get_music_data(self, api_url: str) -> dict:
        ajs = await self._get_a_json(api_url)
        msd_url = ajs["result"]["context"]["MusicData"]["file"]
        async with aiohttp.ClientSession() as session:
            async with session.get(url=msd_url) as r:
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

    async def _get_song_color(self, song_id: int, api_url: str) -> Optional[int]:
        msd_data = await self._get_music_data(api_url)
        for s in msd_data:
            if s["code"] == song_id:
                color = s["albumBgColor"][:-2]
                return int(color, 16)
        return None

    def _generate_embed(
        self,
        artist_name: str,
        song_name: str,
        duration: str,
        image_url: str,
        current_time: datetime,
        color: Optional[Union[int, discord.Color]],
        skills: Optional[str],
    ) -> tuple[discord.Embed, str]:
        embed_title = f"SSL #{current_time.strftime("%w").replace("0", "7")}"

        embed = discord.Embed(
            color=(
                color
                if color is not None
                else discord.Color.random(seed=current_time.timestamp())
            ),
            title=embed_title,
            description=f"**{artist_name} - {song_name}**",
        )

        embed.add_field(
            name="Duration",
            value=duration,
        )
        if skills:
            embed.add_field(
                name="Skill Order",
                value=skills,
            )

        embed.set_thumbnail(url=image_url)
        embed.set_footer(text=current_time.strftime("%A, %B %d, %Y").replace(" 0", " "))

        return embed, embed_title

    async def _unpin_old_ssl(
        self,
        embed_title: str,
        pin_channel: discord.TextChannel,
    ) -> None:
        pins = await pin_channel.pins()
        for pin in pins:
            embeds = pin.embeds
            if embeds and embeds[0].title and embed_title in embeds[0].title:
                await pin.unpin()
                break

    async def _pin_new_ssl(
        self,
        itr: discord.Interaction,
        embed: discord.Embed,
        pin_channel: discord.TextChannel,
    ) -> None:
        msg = await pin_channel.send(embed=embed)
        await asyncio.sleep(1)
        await msg.pin()
        await itr.followup.send("Pinned!")

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.errors.NoPrivateMessage):
            await interaction.response.send_message(
                "This command cannot be used in direct messages",
                ephemeral=True,
                silent=True,
            )
            return

        if isinstance(error, app_commands.errors.MissingAnyRole):
            await interaction.response.send_message(
                "You do not have permission to use this command",
                ephemeral=True,
                silent=True,
            )
            return

        raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(SSLeague(bot))
