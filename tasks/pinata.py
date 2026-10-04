"""Opens a box of prizes every ten minutes on the days that have one."""

import asyncio
import logging
import random
from collections.abc import Callable
from datetime import datetime, time
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

from channels import find_channel
from discord_ids import SUPERSTAR_ROLES
from games.registry import KST
from pinata.config import CHANNELS, PRIZES, Prize
from pinata.lottery import Entries, draw, min_roll
from ui.pinata import WINDOW_SECONDS, BoxView, box_embed, result_embed

if TYPE_CHECKING:
    from bot import dBot

logger = logging.getLogger(__name__)

GUITAR = Path(__file__).resolve().parent.parent / "pinata" / "guitar.png"
NO_ROLE_MENTIONS = discord.AllowedMentions(
    everyone=False, users=True, roles=False, replied_user=False
)


def day_key(moment: datetime) -> str:
    """``MMDD`` of a moment in KST."""
    return f"{moment.astimezone(KST):%m%d}"


GUITAR_PNG = GUITAR.read_bytes()  # 2 KB, and a File is used up by one message


def _guitar() -> discord.File:
    return discord.File(BytesIO(GUITAR_PNG), filename="guitar.png")


class Box:
    """A prize as shown: its role in the guild, if it is one, and its text."""

    def __init__(self, prize: Prize, guild: discord.Guild) -> None:
        role = guild.get_role(prize.role) if isinstance(prize.role, int) else None
        self.role = role
        name = role.name if role else str(prize.role)
        lead = f"{prize.source} " if prize.source else ""
        self.label = f"{lead}{name}"
        self.mention = f"{lead}{role.mention if role else prize.role}"
        self.colour = role.colour if role else None


class Pinata(commands.Cog):
    def __init__(
        self,
        bot: dBot,
        *,
        window: float = WINDOW_SECONDS,
        clock: Callable[[], datetime] = lambda: datetime.now(tz=KST),
        rng: random.Random | None = None,
    ) -> None:
        self.bot = bot
        self.window = window
        self._clock = clock
        self._rng = rng or random.SystemRandom()

    async def cog_load(self) -> None:
        self.open_boxes.start()

    async def cog_unload(self) -> None:
        self.open_boxes.cancel()

    @tasks.loop(
        time=[time(hour=h, minute=m) for h in range(24) for m in range(0, 60, 10)]
    )
    async def open_boxes(self) -> None:
        await self.bot.wait_until_ready()
        prizes = PRIZES.get(day_key(self._clock()), ())
        if not prizes:
            return
        results = await asyncio.gather(
            *(
                self.open_in(guild_id, channel_id, prizes)
                for guild_id, channel_id in CHANNELS.items()
            ),
            return_exceptions=True,
        )
        for error in results:
            if isinstance(error, Exception):
                logger.error("A box failed.", exc_info=error)

    async def open_in(
        self, guild_id: int, channel_id: int, prizes: tuple[Prize, ...]
    ) -> None:
        channel = await find_channel(self.bot, channel_id, discord.TextChannel)
        if channel is None or channel.guild.id != guild_id:
            return
        boxes = [Box(p, channel.guild) for p in prizes]
        entries: Entries[discord.Member | discord.User] = Entries(len(boxes))
        colour = next((b.colour for b in boxes if b.role), None)
        mentions = [b.mention for b in boxes]

        def render() -> discord.Embed:
            return box_embed(mentions, colour, entries)

        view = BoxView([b.label for b in boxes], entries, render, timeout=self.window)
        message = await channel.send(embed=render(), file=_guitar(), view=view)
        await asyncio.sleep(self.window)
        view.close()
        await message.edit(view=view)

        for index, box in enumerate(boxes):
            await self._open(channel, box, index, entries)

    async def _open(
        self,
        channel: discord.TextChannel,
        box: Box,
        index: int,
        entries: Entries[discord.Member | discord.User],
    ) -> None:
        guild = channel.guild
        superstar = box.role is not None and box.role.id in SUPERSTAR_ROLES.get(
            guild.id, ()
        )
        result = draw(entries.for_prize(index), min_roll(superstar), self._rng)
        embed = result_embed(result, box.mention, box.colour, nobody_joined=not entries)
        await channel.send(embed=embed, file=_guitar())
        winner = result.winner
        if winner is None:
            return
        text = f":tada:Congratulations {winner.mention}, you got **{box.mention}**!"
        if box.role is not None and superstar:
            await self.bot.db.roles.add(winner.id, [box.role.id])
            text += "\nThe role has been added to your inventory."
        elif box.role is not None and isinstance(winner, discord.Member):
            try:
                await winner.add_roles(box.role)
                text += "\nThe role has been added to your profile."
            except discord.HTTPException:
                logger.warning("Could not give %s to %d.", box.role.name, winner.id)
                text += "\nI could not give you the role; ask a moderator."
        await channel.send(text, allowed_mentions=NO_ROLE_MENTIONS)


async def setup(bot: dBot) -> None:
    await bot.add_cog(Pinata(bot))
