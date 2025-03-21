import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional, Union
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

from app_commands.autocomplete.ssLeague import (
    _ssl_preprocess,
    artist_autocomplete,
    song_autocomplete,
    song_id_autocomplete,
)
from static.dConsts import GAMES, SSRG_ROLE_MOD, SSRG_ROLE_SS, TEST_ROLE_OWNER

if TYPE_CHECKING:
    from dBot import dBot


@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
class SSLeague(commands.GroupCog, name="ssl", description="Pin SSL song of the day"):
    GAME_CHOICES = [
        app_commands.Choice(name=game["name"], value=key)
        for key, game in GAMES.items()
        if game["pinChannelIds"]
    ]
    _GAME_CHOICES = [
        app_commands.Choice(name=game["name"], value=key)
        for key, game in GAMES.items()
        if game["pinChannelIds"] and key != "SM"
    ]

    def __init__(self, bot: "dBot"):
        self.bot = bot

    @app_commands.command(
        description=(
            "Pin SSL song of the day using Artist Name and Song Name "
            "(Requires SUPERSTAR Role)"
        )
    )
    @app_commands.choices(game=GAME_CHOICES)
    @app_commands.autocomplete(artist_name=artist_autocomplete)
    @app_commands.autocomplete(song_name=song_autocomplete)
    @app_commands.checks.has_any_role(TEST_ROLE_OWNER, SSRG_ROLE_MOD, SSRG_ROLE_SS)
    async def pin_by_name(
        self,
        itr: discord.Interaction["dBot"],
        game: app_commands.Choice[str],
        artist_name: str,
        song_name: str,
    ):
        if not self.bot.info_data_ready:
            return await itr.response.send_message(
                "Song data synchronization in progress, feature unavailable.",
                ephemeral=True,
            )

        await itr.response.defer(ephemeral=True)
        (
            game_details,
            artist_name_index,
            song_name_index,
            song_id_index,
            duration_index,
            image_url_index,
            _,
            skills_index,
        ) = _ssl_preprocess(game.value)

        ssl_song = self.bot.info_by_name[game.value][artist_name][song_name]
        if not ssl_song:
            return await itr.followup.send("Song not found.")

        timezone = game_details["timezone"]
        assert (pin_channel_ids := game_details["pinChannelIds"])
        assert (guild_id := itr.guild_id)
        pin_role = (
            game_details["pinRoles"][guild_id] if game_details["pinRoles"] else None
        )

        await self._handle_ssl_command(
            itr,
            ssl_song[artist_name_index],
            ssl_song[song_name_index],
            int(ssl_song[song_id_index]),
            ssl_song[duration_index],
            ssl_song[image_url_index],
            ssl_song[skills_index] if skills_index else None,
            timezone,
            game_details["resetOffset"],
            pin_channel_ids[guild_id],
            pin_role,
        )

    @app_commands.command(
        description="Pin SSL song of the day using Song ID (Requires SUPERSTAR Role)"
    )
    @app_commands.choices(game=_GAME_CHOICES)
    @app_commands.autocomplete(song_id=song_id_autocomplete)
    @app_commands.checks.has_any_role(TEST_ROLE_OWNER, SSRG_ROLE_MOD, SSRG_ROLE_SS)
    async def pin_by_id(
        self,
        itr: discord.Interaction["dBot"],
        game: app_commands.Choice[str],
        song_id: str,
    ):
        if not self.bot.info_data_ready:
            return await itr.response.send_message(
                "Song data synchronization in progress, feature unavailable.",
                ephemeral=True,
            )

        await itr.response.defer(ephemeral=True)
        (
            game_details,
            artist_name_index,
            song_name_index,
            song_id_index,
            duration_index,
            image_url_index,
            _,
            skills_index,
        ) = _ssl_preprocess(game.value)

        ssl_song = self.bot.info_by_id[game.value][song_id]
        if not ssl_song:
            return await itr.followup.send("Song not found.")

        timezone = game_details["timezone"]
        assert (pin_channel_ids := game_details["pinChannelIds"])
        assert (guild_id := itr.guild_id)
        pin_role = (
            game_details["pinRoles"][guild_id] if game_details["pinRoles"] else None
        )

        await self._handle_ssl_command(
            itr,
            ssl_song[artist_name_index],
            ssl_song[song_name_index],
            int(ssl_song[song_id_index]),
            ssl_song[duration_index],
            ssl_song[image_url_index],
            ssl_song[skills_index] if skills_index else None,
            timezone,
            game_details["resetOffset"],
            pin_channel_ids[guild_id],
            pin_role,
        )

    async def _handle_ssl_command(
        self,
        itr: discord.Interaction["dBot"],
        artist_name: str,
        song_name: str,
        song_id: int,
        duration: str,
        image_url: str,
        skills: Optional[str],
        timezone: ZoneInfo,
        offset: timedelta,
        pin_channel_id: int,
        pin_role: Optional[int],
    ) -> None:
        color: Optional[int] = 0
        color = self._get_song_color(itr.namespace.game, song_id)

        current_time = datetime.now(timezone) - offset
        embed, embed_title = self._generate_embed(
            artist_name,
            song_name,
            duration,
            image_url,
            current_time,
            color,
            skills,
            itr.user.name,
        )

        pin_channel = self.bot.get_channel(pin_channel_id)

        try:
            assert isinstance(pin_channel, discord.TextChannel)
            await self._unpin_old_ssl(embed_title, pin_channel)
            await self._pin_new_ssl(embed, pin_channel)
            topic = f"[{current_time.strftime("%m.%d.%y")}] {artist_name} - {song_name}"
            if pin_role:
                await pin_channel.send(f"<@&{pin_role}> {topic}")
            else:
                await pin_channel.send(topic)
            await pin_channel.edit(topic=topic)
            await itr.followup.send("Pinned!")
        except AssertionError:
            await itr.followup.send("Bot is not in server")

    def _get_song_color(self, game: str, song_id: int) -> Optional[int]:
        msd_data = self.bot.info_color[game]
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
        user_name: str,
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
        embed.set_footer(
            text=(
                f"{current_time.strftime('%A, %B %d, %Y').replace(' 0', ' ')}"
                f" · Pinned by {user_name}"
            )
        )

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
        embed: discord.Embed,
        pin_channel: discord.TextChannel,
    ) -> None:
        msg = await pin_channel.send(embed=embed)
        await asyncio.sleep(1)
        await msg.pin()
        # await asyncio.sleep(1)

        # async for m in pin_channel.history(limit=10):
        #     if m.type == discord.MessageType.pins_add:
        #         await m.delete()
        #         break

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ):
        if isinstance(error, app_commands.errors.MissingAnyRole):
            return await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
            )

        await super().cog_app_command_error(interaction, error)
        raise error


async def setup(bot: "dBot"):
    await bot.add_cog(SSLeague(bot))
