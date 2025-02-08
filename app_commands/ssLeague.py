import asyncio
import gzip
import json
from base64 import b64decode
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import aiohttp
import discord
from Cryptodome.Util.Padding import unpad
from discord import app_commands
from discord.ext import commands

from app_commands.autocomplete.ssLeague import (
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
    sheetService,
    ssCrypt,
)


class SSLeague(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(description="Pin SSL song of the day")
    @app_commands.choices(
        game=[
            app_commands.Choice(name=v["name"], value=k)
            for k, v in GAMES.items()
            if v["pinChannelId"]
        ]
    )
    @app_commands.autocomplete(artist_name=artist_autocomplete)
    @app_commands.autocomplete(song_name=song_autocomplete)
    @app_commands.autocomplete(song_id=song_id_autocomplete)
    @app_commands.checks.has_any_role(OK_ROLE_OWNER, SSRG_ROLE_MOD, SSRG_ROLE_SS)
    async def ssl(
        self,
        itr: discord.Interaction,
        game: app_commands.Choice[str],
        artist_name: Optional[str],
        song_name: Optional[str],
        song_id: Optional[str],
    ):
        await itr.response.defer(ephemeral=True)
        if not song_id and not (artist_name and song_name):
            await itr.followup.send(
                "Pinning SSL requires one of the following:"
                "\n- Artist Name and Song Name"
                "\n- Song ID",
                ephemeral=True,
            )
        else:
            gameD = GAMES[game.value]
            result = (
                sheetService.values()
                .get(
                    spreadsheetId=gameD["sslId"],
                    range=gameD["sslRange"],
                )
                .execute()
            )
            songs = result.get("values", [])

            try:
                song = next(
                    s
                    for s in songs
                    if s[gameD["sslColumns"].index("song_id")] == str(song_id)
                    or (
                        not song_id
                        and s[gameD["sslColumns"].index("artist_name")].lower()
                        == artist_name.lower()
                        and s[gameD["sslColumns"].index("song_name")].lower()
                        == song_name.lower()
                    )
                )

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url=gameD["api"],
                        headers=A_JSON_HEADERS,
                        data=A_JSON_BODY,
                    ) as r:
                        js = await r.json(content_type=None)
                        msd_url = js["result"]["context"]["MusicData"]["file"]

                    async with session.get(url=msd_url) as r:
                        msd_enc = b""
                        while True:
                            chunk = await r.content.read(1024)
                            if not chunk:
                                break
                            msd_enc += chunk

                msd_enc = gzip.decompress(msd_enc)
                msd_dec = (
                    unpad(ssCrypt.decrypt(b64decode(msd_enc)), 16)
                    .replace(rb"\/", rb"/")
                    .replace(rb"\u", rb"ddm135-u")
                )
                js = json.loads(msd_dec)
                msd_dec = (
                    json.dumps(js, indent="\t", ensure_ascii=False)
                    .replace(r"ddm135-u", r"\u")
                    .encode("utf8")
                )
                msd_data = json.loads(msd_dec)

                color = None
                for s in msd_data:
                    if str(s["code"]) == song[gameD["sslColumns"].index("song_id")]:
                        color = s["albumBgColor"][:-2]
                        color = int(color, 16)
                        break
                current_time = datetime.now(ZoneInfo(gameD["timezone"])) - gameD["sslOffset"]
                embed_title = f"SSL #{current_time.strftime("%w").replace("0", "7")}"

                embed = discord.Embed(
                    color=color or discord.Color.random(seed=current_time.timestamp()),
                    title=embed_title,
                    description=(
                        f"**{song[gameD["sslColumns"].index("artist_name")]} - "
                        f"{song[gameD["sslColumns"].index("song_name")]}**"
                    ),
                )

                embed.add_field(
                    name="Duration",
                    value=song[gameD["sslColumns"].index("duration")],
                )
                if "skills" in gameD["sslColumns"]:
                    embed.add_field(
                        name="Skill Order",
                        value=song[gameD["sslColumns"].index("skills")],
                    )
                embed.set_thumbnail(url=song[gameD["sslColumns"].index("image")])
                embed.set_footer(
                    text=current_time.strftime("%A, %B %d, %Y").replace(" 0", " ")
                )

                pin_channel = self.bot.get_channel(gameD["pinChannelId"])
                pins = await pin_channel.pins()
                for pin in pins:
                    embeds = pin.embeds
                    if embeds and embed_title in embeds[0].title:
                        await pin.unpin()
                        break

                msg = await pin_channel.send(embed=embed)
                await asyncio.sleep(1)
                await msg.pin()
                await itr.followup.send("Pinned!")
            except StopIteration:
                await itr.followup.send("Song not found")
            except AttributeError:
                await itr.followup.send("Bot is not in server")

    async def cog_app_command_error(self, interaction: discord.Interaction, error):
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


async def setup(bot: commands.Bot):
    await bot.add_cog(SSLeague(bot))
