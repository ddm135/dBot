"""``/info``: song lengths, and details about one song."""

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from games.decks import Deck, Song
from games.index import Index
from games.song_stats import SongStat
from ui.images import Upload, files, prepare
from ui.pages import Paginator, page_count, slice_page
from ui.song import song_embed
from ui.text import escape

from .common import (
    NO_DATA,
    Itr,
    choose_artist,
    deck_autocomplete,
    game_choices,
    icon_for,
    parse_code,
    song_autocomplete,
)

if TYPE_CHECKING:
    from bot import dBot

PER_PAGE = 10
UNKNOWN_SORT = 10**9
STANDARD_LEVELS = "Easy / Hard / Normal"


def length_key(stat: SongStat | None) -> int:
    return stat.seconds if stat and stat.seconds is not None else UNKNOWN_SORT


def sort_by_length(songs: list[Song], stats: dict[int, SongStat]) -> list[Song]:
    """Shortest first; songs without a known length go last."""
    return sorted(
        songs,
        key=lambda s: (length_key(stats.get(s.code)), s.deck_code, s.name, s.code),
    )


def song_line(
    song: Song, stat: SongStat | None, deck: Deck | None, *, show_deck: bool
) -> str:
    duration = stat.duration if stat else "Unknown"
    name = f"**{escape(song.label)}**"
    prefix = f"{escape(deck.name)} - " if show_deck and deck else ""
    return f"({duration}) {prefix}{name}"


def list_embed(
    index: Index,
    title: str,
    songs: list[Song],
    stats: dict[int, SongStat],
    icon: str | None,
    page: int,
    pages: int,
    *,
    show_deck: bool,
) -> discord.Embed:
    shown = slice_page(songs, page, PER_PAGE)
    embed = discord.Embed(
        title=title,
        description="\n".join(
            song_line(
                s,
                stats.get(s.code),
                index.decks.decks.get(s.deck_code),
                show_deck=show_deck,
            )
            for s in shown
        ),
        color=index.game.color,
    )
    embed.set_author(name=f"{index.game.name} - Song Length", icon_url=icon)
    embed.set_footer(text=f"Page {page}/{pages}")
    return embed


def detail_embed(
    index: Index,
    deck: Deck,
    song: Song,
    stat: SongStat | None,
    icon: str | None,
    thumbnail: str | None = None,
) -> discord.Embed:
    game = index.game
    embed = song_embed(index, deck, song, stat, "Song Info", icon, thumbnail)
    if stat and stat.notes:
        levels = " / ".join(sorted(stat.notes))
        if levels != STANDARD_LEVELS:
            embed.add_field(name="Difficulty Levels", value=levels)
        counts = " / ".join(f"{n:,}" for n in sorted(stat.notes.values()))
    else:
        counts = "Unknown"
    embed.add_field(name="Note Count", value=counts)
    embed.add_field(name="Album", value=escape(song.album or "Unknown"), inline=False)
    embed.add_field(
        name="Release Date",
        value=game.format_date(song.release) if song.release else "Unknown",
    )
    record = song.raw.get("myrecordQualifyingScore")
    if isinstance(record, int) and record:
        embed.add_field(name="My Record Challenge Score", value=f"{record:,}")
    return embed


class Info(commands.Cog):
    def __init__(self, bot: dBot) -> None:
        self.bot = bot

    @app_commands.command()
    @app_commands.choices(game=game_choices())
    @app_commands.autocomplete(artist=deck_autocomplete, song=song_autocomplete)
    async def info(
        self,
        itr: Itr,
        game: app_commands.Choice[str],
        artist: str | None = None,
        song: str | None = None,
    ) -> None:
        """View song durations from shortest to longest.

        If a song is provided, view detailed information about the song.

        Parameters
        ----------
        game: Game
        artist: Artist/Album
        song: Song
        """
        await itr.response.defer()
        index = self.bot.indexes.get(game.value)
        if index is None:
            await itr.followup.send(NO_DATA)
            return
        stats = dict(await self.bot.stats.get(game.value))
        game_icon = icon_for(self.bot, game.value)
        icon = game_icon
        uploads: list[Upload] = []

        deck: Deck | None = None
        if artist is None and song is not None:
            # Only the song: its artist is the song's own.
            owner = index.decks.songs.get(parse_code(song) or -1)
            if owner is None:
                await itr.followup.send("Song not found.")
                return
            artist = str(owner.deck_code)
        if artist is not None:
            if (
                chosen := await choose_artist(self.bot, itr, index, artist, icon)
            ) is None:
                return
            deck, icon, uploads = chosen

        if song is not None:
            assert deck is not None  # chosen above, from the song if need be
            found = index.decks.songs.get(parse_code(song) or -1)
            if found is None or found.deck_code != deck.code:
                await itr.followup.send("Song not found.")
                return
            album = await self.bot.images.album(game.value, found.code)
            thumbnail, more = prepare(album, None, "album")
            await itr.followup.send(
                embed=detail_embed(
                    index, deck, found, stats.get(found.code), icon, thumbnail
                ),
                files=files(uploads + more),
            )
            return

        songs = sort_by_length(
            list(deck.songs) if deck else list(index.decks.songs.values()), stats
        )
        if not songs:
            await itr.followup.send("No songs found.")
            return
        title = escape(deck.name) if deck else "All Songs"
        pages = page_count(len(songs), PER_PAGE)

        def render(page: int, total: int) -> discord.Embed:
            return list_embed(
                index, title, songs, stats, icon, page, total, show_deck=deck is None
            )

        await Paginator(itr.user, render, pages).start(itr, files=files(uploads))


async def setup(bot: dBot) -> None:
    await bot.add_cog(Info(bot))
