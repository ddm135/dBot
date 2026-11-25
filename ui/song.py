"""The start of every song embed."""

import discord

from games.bonus.decks import Deck, Song
from games.charts.song_stats import SongStat
from games.index import Index

from .text import escape, md


def song_embed(
    index: Index,
    deck: Deck,
    song: Song,
    stat: SongStat | None,
    author: str,
    icon: str | None,
    thumbnail: str | None = None,
) -> discord.Embed:
    """The artist and song, the game as author, and the song's duration."""
    colour = index.album_color(song.code)  # black is a colour too
    embed = discord.Embed(
        title=escape(deck.name),
        description=md(t"**{song.label}**"),
        color=index.game.color if colour is None else colour,
    )
    embed.set_author(name=f"{index.game.name} - {author}", icon_url=icon)
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    embed.add_field(name="Duration", value=stat.duration if stat else "Unknown")
    return embed
