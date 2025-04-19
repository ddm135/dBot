from datetime import datetime
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from app_commands.autocomplete.ssleague import (
    artist_autocomplete,
    song_autocomplete,
    song_id_autocomplete,
)
from statics.consts import GAMES, SSRG_ROLE_MOD, SSRG_ROLE_SS, TEST_ROLE_OWNER
from statics.helpers import generate_ssl_embed, pin_new_ssl, unpin_old_ssl

if TYPE_CHECKING:
    from dBot import dBot
    from statics.types import GameDetails


@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
class SSLeague(commands.GroupCog, name="ssl", description="Pin SSL song of the day"):
    GAME_CHOICES = [
        app_commands.Choice(name=game["name"], value=key)
        for key, game in GAMES.items()
        if game["pinChannelIds"]
    ]

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    @app_commands.command()
    @app_commands.choices(game_choice=GAME_CHOICES)
    @app_commands.autocomplete(artist_name=artist_autocomplete)
    @app_commands.autocomplete(song_name=song_autocomplete)
    @app_commands.rename(game_choice="game", artist_name="artist", song_name="song")
    @app_commands.checks.has_any_role(TEST_ROLE_OWNER, SSRG_ROLE_MOD, SSRG_ROLE_SS)
    async def pin_by_name(
        self,
        itr: discord.Interaction["dBot"],
        game_choice: app_commands.Choice[str],
        artist_name: str,
        song_name: str,
    ) -> None:
        """Pin SSL song of the day using Artist Name and Song Name
        (Requires SUPERSTAR Role)

        Parameters
        -----------
        game_choice: Choice[:class:`str`]
            Game
        artist_name: :class:`str`
            Artist Name
        song_name: :class:`str`
            Song Name
        """

        await itr.response.defer(ephemeral=True)
        if not self.bot.info_data_ready:
            return await itr.followup.send(
                "Song data synchronization in progress, feature unavailable.",
            )

        game = game_choice.value
        game_details = GAMES[game]
        assert (guild_id := itr.guild_id)
        pin_channel_id = game_details["pinChannelIds"].get(guild_id)
        if not pin_channel_id:
            return await itr.followup.send(
                f"Pin channel for {game_choice.name} is not set for this server.",
            )

        info_columns = game_details["infoColumns"]
        song_id_index = info_columns.index("song_id")
        duration_index = info_columns.index("duration")
        skills_index = (
            info_columns.index("skills") if "skills" in info_columns else None
        )

        ssl_song = self.bot.info_by_name[game][artist_name][song_name]
        if not ssl_song:
            return await itr.followup.send("Song not found.")

        await self.handle_ssl_command(
            itr,
            artist_name,
            song_name,
            int(ssl_song[song_id_index]),
            ssl_song[duration_index],
            ssl_song[skills_index] if skills_index is not None else None,
            pin_channel_id,
            game_details,
        )

    @app_commands.command()
    @app_commands.choices(game_choice=GAME_CHOICES)
    @app_commands.autocomplete(song_id=song_id_autocomplete)
    @app_commands.rename(game_choice="game", song_id="id")
    @app_commands.checks.has_any_role(TEST_ROLE_OWNER, SSRG_ROLE_MOD, SSRG_ROLE_SS)
    async def pin_by_id(
        self,
        itr: discord.Interaction["dBot"],
        game_choice: app_commands.Choice[str],
        song_id: str,
    ) -> None:
        """Pin SSL song of the day using Song ID
        (Requires SUPERSTAR Role)

        Parameters
        -----------
        game_choice: Choice[:class:`str`]
            Game
        song_id: :class:`str`
            Song ID
        """

        await itr.response.defer(ephemeral=True)
        if not self.bot.info_data_ready:
            return await itr.followup.send(
                "Song data synchronization in progress, feature unavailable.",
            )

        game = game_choice.value
        game_details = GAMES[game]
        assert (guild_id := itr.guild_id)
        pin_channel_id = game_details["pinChannelIds"].get(guild_id)
        if not pin_channel_id:
            return await itr.followup.send(
                f"Pin channel for {game_choice.name} is not set for this server.",
            )

        info_columns = game_details["infoColumns"]
        artist_name_index = info_columns.index("artist_name")
        song_name_index = info_columns.index("song_name")
        duration_index = info_columns.index("duration")
        skills_index = (
            info_columns.index("skills") if "skills" in info_columns else None
        )

        ssl_song = self.bot.info_by_id[game][song_id]
        if not ssl_song:
            return await itr.followup.send("Song not found.")

        await self.handle_ssl_command(
            itr,
            ssl_song[artist_name_index],
            ssl_song[song_name_index],
            int(song_id),
            ssl_song[duration_index],
            ssl_song[skills_index] if skills_index is not None else None,
            pin_channel_id,
            game_details,
        )

    async def handle_ssl_command(
        self,
        itr: discord.Interaction["dBot"],
        artist_name: str,
        song_name: str,
        song_id: int,
        duration: str,
        skills: str | None,
        pin_channel_id: int,
        game_details: "GameDetails",
    ) -> None:
        game = itr.namespace.game
        artist_name = artist_name.replace(r"*", r"\*").replace(r"_", r"\_")
        song_name = song_name.replace(r"*", r"\*").replace(r"_", r"\_")
        timezone = game_details["timezone"]
        offset = game_details["resetOffset"]
        assert (guild_id := itr.guild_id)
        pin_role = game_details["pinRoles"].get(guild_id)

        color = game_details["color"]
        image_url = None

        msd_data = self.bot.info_msd[game]
        for song in msd_data:
            if song["code"] == song_id:
                color = int(song["albumBgColor"][:-2], 16)
                image_url = song["album"]
                break

        if game_details["legacyUrlScheme"]:
            url_data = self.bot.info_url[game]
            for url in url_data:
                if url["code"] == image_url:
                    image_url = url["url"]
                    break

        current_time = datetime.now(tz=timezone) - offset
        embed = generate_ssl_embed(
            artist_name,
            song_name,
            duration,
            image_url,
            color,
            skills,
            current_time,
            itr.user.name,
        )

        pin_channel = self.bot.get_channel(pin_channel_id)

        assert isinstance(pin_channel, discord.TextChannel)
        new_pin = await pin_new_ssl(embed, pin_channel)
        topic = f"[{current_time.strftime("%m.%d.%y")}] {artist_name} - {song_name}"
        if pin_role:
            await pin_channel.send(f"<@&{pin_role}> {topic}")
        else:
            await pin_channel.send(topic)
        await pin_channel.edit(topic=topic)
        await itr.followup.send("Pinned!")
        await unpin_old_ssl(
            embed.title,  # type: ignore[arg-type]
            pin_channel,
            new_pin,
        )

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, app_commands.errors.MissingAnyRole):
            return await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
            )

        await super().cog_app_command_error(interaction, error)
        raise error


async def setup(bot: "dBot") -> None:
    await bot.add_cog(SSLeague(bot))
