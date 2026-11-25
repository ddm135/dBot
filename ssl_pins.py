"""Posting and pinning the SSL song of the day."""

import asyncio
import logging
from collections.abc import Iterable
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING

import discord

from db.ssl import LastAppearance
from games.bonus.decks import Deck, Song
from games.charts.song_stats import SongStat
from games.index import Index
from games.models import Game
from ui.images import Upload, files, prepare
from ui.song import song_embed
from ui.text import long_date, timestamp

if TYPE_CHECKING:
    from bot import dBot

logger = logging.getLogger(__name__)

RESET_OFFSET = timedelta(hours=2)  # the game's day starts two hours late
RESET_HOUR = 2
PIN_DELAY = 1.0  # a short pause so the message exists before it is pinned


def ssl_day(game: Game) -> datetime:
    """The current SSL day, as a time in the game's timezone."""
    return game.now() - RESET_OFFSET


def slot_name(game: Game, when: datetime) -> str:
    """``SSL #3``: the weekday number of the day (Monday is 1)."""
    return f"SSL #{when.isoweekday()}"


def reset_time(game: Game, last: date | None) -> datetime | None:
    """The moment the SSL of a past day started, for the "last seen" fields."""
    day = last
    if day is None:
        return None
    return datetime.combine(day, time(RESET_HOUR), tzinfo=game.timezone)


def last_text(moment: datetime | None) -> str:
    if moment is None:
        return "N/A"
    return f"{long_date(moment)} ({timestamp(moment)})"


def build_embed(
    index: Index,
    deck: Deck,
    song: Song,
    stat: SongStat | None,
    icon: str | None,
    when: datetime,
    pinner: str,
    last: LastAppearance,
    thumbnail: str | None = None,
) -> discord.Embed:
    game = index.game
    embed = song_embed(index, deck, song, stat, slot_name(game, when), icon, thumbnail)
    counts = (
        " / ".join(
            str(n) for n in stat.notes.values()
        )  # in chart order, as v0 showed them
        if stat and stat.notes
        else "Unknown"
    )
    embed.add_field(name="Note Count", value=counts)
    embed.add_field(
        name="Artist Last Appearance",
        value=last_text(reset_time(game, last.deck)),
        inline=False,
    )
    embed.add_field(
        name="Song Last Appearance",
        value=last_text(reset_time(game, last.song)),
        inline=False,
    )
    embed.set_footer(text=f"{long_date(when)} · Pinned by {pinner}")
    return embed


def topic_text(deck: Deck, song: Song, when: datetime) -> str:
    return f"[{when:%m.%d.%y}] {deck.name} - {song.label}"


class PinError(Exception):
    """The pin channel cannot be used."""


class SslPinner:
    def __init__(self, bot: dBot) -> None:
        self.bot = bot

    async def pin(
        self,
        game: Game,
        song_code: int,
        guild_ids: Iterable[int],
        pinner: str,
    ) -> list[int]:
        """Post and pin the song in each guild that has a pin channel.

        Returns the guilds it was pinned in. Raises ``LookupError`` when the
        song is not in the game's data.
        """
        index = self.bot.indexes.get(game.key)
        song = index.decks.songs.get(song_code) if index else None
        deck = index.decks.decks.get(song.deck_code) if index and song else None
        if index is None or song is None or deck is None:
            raise LookupError(f"Song {song_code} is not in the {game.key} data.")

        when = ssl_day(game)
        stat = (await self.bot.stats.get(game.key)).get(song.code)
        emblem = await self.bot.images.emblem(game.key, deck.code)
        icon, uploads = prepare(emblem, self.bot.games.get(game.key).icon_url, "emblem")
        thumbnail, more = prepare(
            await self.bot.images.album(game.key, song.code), None, "album"
        )
        uploads += more
        last = await self.bot.db.ssl.last(
            game.key, song.code, deck.code, before=when.date()
        )
        embed = build_embed(
            index, deck, song, stat, icon, when, pinner, last, thumbnail
        )
        topic = topic_text(deck, song, when)

        pinned = []
        for guild_id in guild_ids:
            target = game.pins.get(guild_id)
            if target is None:
                continue
            try:
                await self._pin_in(
                    game, target.channel_id, target.role_id, embed, topic, when, uploads
                )
            except discord.HTTPException, PinError:
                logger.exception("%s: Could not pin in guild %d.", game.key, guild_id)
                continue
            pinned.append(guild_id)
        if pinned:
            await self.bot.db.ssl.record(game.key, when.date(), song.code, deck.code)
        return pinned

    async def _pin_in(
        self,
        game: Game,
        channel_id: int,
        role_id: int | None,
        embed: discord.Embed,
        topic: str,
        when: datetime,
        uploads: list[Upload],
    ) -> None:
        channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(
            channel_id
        )
        if not isinstance(channel, discord.TextChannel):
            raise PinError(f"Channel {channel_id} is not a text channel.")
        message = await channel.send(embed=embed, files=files(uploads))
        await asyncio.sleep(PIN_DELAY)
        await message.pin()
        await channel.send(f"<@&{role_id}> {topic}" if role_id else topic)
        await channel.edit(topic=topic)
        await self._unpin_old(channel, message.id, f"{game.name} - SSL #")

    async def _unpin_old(
        self, channel: discord.TextChannel, new_id: int, author_prefix: str
    ) -> None:
        """Unpin the game's earlier SSL posts, so only today's stays pinned."""
        assert self.bot.user
        async for pin in channel.pins():
            if pin.id == new_id or pin.author.id != self.bot.user.id:
                continue
            if pin.embeds and (pin.embeds[0].author.name or "").startswith(
                author_prefix
            ):
                try:
                    await pin.unpin()
                except discord.HTTPException:
                    logger.warning("Could not unpin message %d.", pin.id, exc_info=True)
