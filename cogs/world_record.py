"""``/world_record``: the best scores of a season."""

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from games.api.world_records import Leaderboard, Record, WorldRecordError
from games.bonus.decks import Deck
from games.bonus.schedule import (
    SeasonError,
    check_weekly,
    current_monday,
    latest_season,
    quarterly_seasons,
    season_code_of,
)
from games.index import Index
from games.models import Game
from games.registry import GAMES
from ui.images import Upload, files, prepare
from ui.pages import Paginator
from ui.world_record import PER_PAGE, artist_embed, leaderboard_embed, page_total

from .common import (
    NO_DATA,
    Itr,
    deck_autocomplete,
    deck_of,
    game_choices,
    parse_code,
    selected_game,
    song_autocomplete,
)

if TYPE_CHECKING:
    from bot import dBot

NOT_AVAILABLE = "World records are not available for this game."
FIRST_WEEKLY_SEASON = 20241202


async def season_autocomplete(itr: Itr, current: str) -> list[app_commands.Choice[int]]:
    key = selected_game(itr)
    if key is None:
        return []
    game = GAMES[key]
    data = itr.client.games.get(key)
    seasons = quarterly_seasons(data.tables, game.timezone, game.now())
    choices = [
        app_commands.Choice(
            name=(
                f"Season {code} ({game.format_date(season.start)} - "
                f"{game.format_date(season.end)})"
            ),
            value=code,
        )
        for code, season in reversed(
            seasons.items()
        )  # the newest are the ones people want
        if current in str(code)
    ]
    return choices[:25]


class WorldRecord(
    commands.GroupCog, name="world_record", description="View world records"
):
    def __init__(self, bot: dBot) -> None:
        self.bot = bot

    async def _start(self, itr: Itr, game_key: str) -> tuple[Game, Index, str] | None:
        """The game, its index and the rank server, or None after saying why not."""
        game = GAMES[game_key]
        index = self.bot.indexes.get(game_key)
        if index is None:
            await itr.followup.send(NO_DATA)
            return None
        manifest = self.bot.games.get(game_key).manifest
        base = manifest.music_rank_server_url if manifest else None
        if not base:
            await itr.followup.send(NOT_AVAILABLE)
            return None
        return game, index, base

    # -- quarterly seasons -----------------------------------------------------

    @app_commands.command(name="quarterly")
    @app_commands.choices(game=game_choices(lambda g: g.has_quarterly_seasons))
    @app_commands.autocomplete(artist=deck_autocomplete, song=song_autocomplete)
    @app_commands.autocomplete(season=season_autocomplete)
    async def quarterly(
        self,
        itr: Itr,
        game: app_commands.Choice[str],
        artist: str,
        song: str | None = None,
        season: int | None = None,
    ) -> None:
        """View world records for games that follow the quarterly season system.

        If a song is provided, view its Top 100, else view the Top 1 of every song.

        Parameters
        ----------
        game: Game
        artist: Artist/Album
        song: Song (requires artist/album to be set)
        season: Season code (defaults to the latest season)
        """
        await itr.response.defer()
        if not (start := await self._start(itr, game.value)):
            return
        info, index, base = start
        deck = deck_of(index, artist)
        if deck is None:
            await itr.followup.send("Artist not found.")
            return
        seasons = quarterly_seasons(
            self.bot.games.get(game.value).tables, info.timezone, info.now()
        )
        code = latest_season(seasons) if season is None else season
        if code is None or code not in seasons:
            await itr.followup.send("Season not found.")
            return

        emblem = await self.bot.images.emblem(game.value, deck.code)
        icon, uploads = prepare(
            emblem, self.bot.games.get(game.value).icon_url, "emblem"
        )

        try:
            if song is not None:
                await self._song(
                    itr, info, index, base, deck, song, code, icon, uploads
                )
            else:
                await self._artist(itr, info, base, deck, code, icon, uploads)
        except WorldRecordError:
            await itr.followup.send("The world record server could not be reached.")

    async def _song(
        self,
        itr: Itr,
        game: Game,
        index: Index,
        base: str,
        deck: Deck,
        song_value: str,
        season: int,
        icon: str | None,
        uploads: list[Upload],
    ) -> None:
        song = index.decks.songs.get(parse_code(song_value) or -1)
        if song is None or song.deck_code != deck.code:
            await itr.followup.send("Song not found.")
            return
        board = await self.bot.world_records.fetch(
            base, season, song.code, game.timezone
        )
        album = await self.bot.images.album(game.key, song.code)
        thumbnail, more = prepare(album, None, "album")
        await self._show_board(
            itr, game, deck, song.label, season, board, thumbnail, icon, uploads + more
        )

    async def _artist(
        self,
        itr: Itr,
        game: Game,
        base: str,
        deck: Deck,
        season: int,
        icon: str | None,
        uploads: list[Upload],
    ) -> None:
        songs = deck.visible_songs
        results = await self.bot.world_records.fetch_many(
            base, season, [s.code for s in songs], game.timezone, first_only=True
        )
        rows: list[tuple[str, Record | str]] = []
        updated = None
        for song in songs:
            result = results[song.code]
            if isinstance(result, WorldRecordError):
                rows.append((song.label, "Error"))
            elif not result.records:
                rows.append((song.label, "None"))
            else:
                rows.append((song.label, result.records[0]))
            if not isinstance(result, WorldRecordError) and result.updated:
                updated = max(updated, result.updated) if updated else result.updated

        def render(page: int, _: int) -> discord.Embed:
            return artist_embed(game, deck.name, season, rows, updated, icon, page)

        await Paginator(itr.user, render, page_total(len(rows))).start(
            itr, files=files(uploads)
        )

    # -- weekly seasons --------------------------------------------------------

    @app_commands.command(name="weekly")
    @app_commands.choices(game=game_choices(lambda g: g.has_weekly_seasons))
    @app_commands.autocomplete(artist=deck_autocomplete)
    async def weekly(
        self,
        itr: Itr,
        game: app_commands.Choice[str],
        artist: str,
        season: app_commands.Range[int, FIRST_WEEKLY_SEASON] | None = None,
    ) -> None:
        """View world records for games that follow the weekly season system.

        Parameters
        ----------
        game: Game
        artist: Artist/Album
        season: Season code (YYYYMMDD, Mondays only, defaults to the latest season)
        """
        await itr.response.defer()
        if not (start := await self._start(itr, game.value)):
            return
        info, index, base = start
        deck = deck_of(index, artist)
        if deck is None:
            await itr.followup.send("Artist not found.")
            return
        today = info.now().date()
        assert info.first_season is not None  # a weekly game has one
        if season is None:
            code = season_code_of(current_monday(today))
        else:
            try:
                check_weekly(season, info.first_season, today)
            except SeasonError as exc:
                await itr.followup.send(str(exc))
                return
            code = season

        emblem = await self.bot.images.emblem(game.value, deck.code)
        icon, uploads = prepare(
            emblem, self.bot.games.get(game.value).icon_url, "emblem"
        )
        try:
            board = await self.bot.world_records.fetch(
                base, code, deck.code, info.timezone
            )
        except WorldRecordError:
            await itr.followup.send("The world record server could not be reached.")
            return
        await self._show_board(itr, info, deck, None, code, board, None, icon, uploads)

    async def _show_board(
        self,
        itr: Itr,
        game: Game,
        deck: Deck,
        song: str | None,
        season: int,
        board: Leaderboard,
        thumbnail: str | None,
        icon: str | None,
        uploads: list[Upload],
    ) -> None:
        def render(page: int, _: int) -> discord.Embed:
            return leaderboard_embed(
                game,
                deck.name,
                song,
                season,
                board.records,
                board.updated,
                thumbnail,
                icon,
                page,
            )

        pages = page_total(len(board.records))
        await Paginator(itr.user, render, pages).start(itr, files=files(uploads))


__all__ = ["PER_PAGE", "WorldRecord", "setup"]


async def setup(bot: dBot) -> None:
    await bot.add_cog(WorldRecord(bot))
