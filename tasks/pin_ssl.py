import asyncio
import json
from datetime import datetime, time
from typing import TYPE_CHECKING

import aiohttp
import discord
from discord.ext import commands, tasks

from statics.consts import CREDENTIALS_DATA, GAMES, SUPERSTAR_HEADERS
from statics.helpers import decrypt_cbc, encrypt_cbc

if TYPE_CHECKING:
    from dBot import dBot


class PinSSL(commands.Cog):
    ALLOWED_GAME = ["SM_JP"]

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.pin_ssl.start()
        await super().cog_load()

    async def cog_unload(self) -> None:
        self.pin_ssl.cancel()
        await super().cog_unload()

    @tasks.loop(time=[time(hour=h, second=1) for h in range(24)])
    async def pin_ssl(self) -> None:
        with open(CREDENTIALS_DATA, "r") as f:
            all_credentials = json.load(f)

        current_date = datetime.now()

        for game in self.ALLOWED_GAME:
            game_details = GAMES[game]

            ssl_date = current_date - game_details["resetOffset"]
            if ssl_date.hour != 0:
                continue

            credentials = all_credentials[game]
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url=game_details["api"],
                    headers=SUPERSTAR_HEADERS,
                    data=encrypt_cbc(
                        f'{"{"}"class":"Account","method":"login","params":[1,'
                        f'"{credentials["username"]}","{credentials["password"]}"'
                        f',1,"{credentials["version"]}",false,-1]{"}"}'
                    ),
                ) as r:
                    try:
                        account = await r.json(content_type=None)
                    except json.JSONDecodeError:
                        account = json.loads(decrypt_cbc(await r.text()))

                oid = account["result"]["user"]["objectID"]
                key = account["invoke"][0]["params"][0]

                async with session.post(
                    url=game_details["api"],
                    headers=SUPERSTAR_HEADERS,
                    data=encrypt_cbc(
                        f'{"{"}"class":"StarLeague","method":"getWeekPlayMusic",'
                        f'"params":[{oid},"{key}"]{"}"}'
                    ),
                ) as r:
                    try:
                        ssleague = await r.json(content_type=None)
                    except json.JSONDecodeError:
                        ssleague = json.loads(decrypt_cbc(await r.text()))

            curday = ssleague["result"]["curday"]
            music_list = ssleague["result"]["musicList"]
            music = next(music for music in music_list if music["day"] == curday)
            song_id = music["music"]
            ssl_song = self.bot.info_by_id[game][song_id]

            info_columns = game_details["infoColumns"]
            artist_name_index = info_columns.index("artist_name")
            song_name_index = info_columns.index("song_name")
            duration_index = info_columns.index("duration")
            skills_index = (
                info_columns.index("skills") if "skills" in info_columns else None
            )

            artist_name = (
                ssl_song[artist_name_index].replace(r"*", r"\*").replace(r"_", r"\_")
            )
            song_name = (
                ssl_song[song_name_index].replace(r"*", r"\*").replace(r"_", r"\_")
            )
            song_id = int(song_id)
            duration = ssl_song[duration_index]
            skills = ssl_song[skills_index] if skills_index is not None else None

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

            timezone = game_details["timezone"]
            offset = game_details["resetOffset"]
            current_time = datetime.now(tz=timezone) - offset

            embed_title = f"SSL #{curday}"
            embed = discord.Embed(
                color=color,
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
                    f"{current_time.strftime("%A, %B %d, %Y").replace(" 0", " ")}"
                    f" · Pinned by {self.bot.user.name}"
                )
            )

            pin_channels = game_details["pinChannelIds"]
            pin_roles = game_details["pinRoles"]
            for guild_id, channel_id in pin_channels.items():
                if not channel_id:
                    continue

                pin_channel = self.bot.get_channel(channel_id)
                assert isinstance(pin_channel, discord.TextChannel)
                new_pin = await self.pin_new_ssl(embed, pin_channel)
                topic = (
                    f"[{current_time.strftime("%m.%d.%y")}] {artist_name} - {song_name}"
                )
                if pin_role := pin_roles.get(guild_id):
                    await pin_channel.send(f"<@&{pin_role}> {topic}")
                else:
                    await pin_channel.send(topic)
                await pin_channel.edit(topic=topic)
                await self.unpin_old_ssl(embed_title, pin_channel, new_pin)

    async def unpin_old_ssl(
        self, embed_title: str, pin_channel: discord.TextChannel, new_pin: int
    ) -> None:
        pins = await pin_channel.pins()
        for pin in pins:
            if pin.id == new_pin:
                continue
            embeds = pin.embeds
            if embeds and embeds[0].title and embed_title in embeds[0].title:
                await pin.unpin()
                break

    async def pin_new_ssl(
        self,
        embed: discord.Embed,
        pin_channel: discord.TextChannel,
    ) -> int:
        msg = await pin_channel.send(embed=embed)
        await asyncio.sleep(1)
        await msg.pin()
        return msg.id

    @pin_ssl.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: "dBot") -> None:
    await bot.add_cog(PinSSL(bot))
