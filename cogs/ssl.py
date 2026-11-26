"""``/ssl``: pin the SSL song of the day by hand."""

from typing import TYPE_CHECKING

from discord import app_commands
from discord.ext import commands

from games.registry import GAMES

from .common import (
    Itr,
    deck_autocomplete,
    game_choices,
    has_pins,
    parse_code,
    song_autocomplete,
)

if TYPE_CHECKING:
    from bot import dBot


async def song_id_autocomplete(
    itr: Itr, current: str
) -> list[app_commands.Choice[str]]:
    """A song code is only offered once it is typed in full and exists."""
    from .common import selected_game

    key = selected_game(itr)
    code = parse_code(current)
    index = itr.client.indexes.get(key) if key else None
    song = index.decks.songs.get(code) if index and code is not None else None
    if song is None or index is None:
        return []
    deck = index.decks.decks[song.deck_code]
    return [
        app_commands.Choice(
            name=f"{song.code}: {deck.name} - {song.name}"[:100], value=str(song.code)
        )
    ]


@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.allowed_installs(guilds=True, users=False)
class SSLeague(commands.GroupCog, name="ssl", description="Pin SSL song of the day"):
    """``/ssl``: pin the SSL song of the day by hand, by artist and song or by song id."""

    def __init__(self, bot: dBot) -> None:
        self.bot = bot

    async def _pin(self, itr: Itr, game_key: str, song_code: int | None) -> None:
        await itr.response.defer(ephemeral=True)
        assert itr.guild_id
        game = GAMES[game_key]
        if itr.guild_id not in game.pins:
            await itr.followup.send(
                f"Pin channel for {game.name} is not set for this server."
            )
            return
        index = self.bot.indexes.get(game_key)
        if index is None or song_code is None or song_code not in index.decks.songs:
            await itr.followup.send("Song not found.")
            return
        try:
            pinned = await self.bot.ssl.pin(
                game, song_code, [itr.guild_id], itr.user.name
            )
        except LookupError:
            await itr.followup.send("Song not found.")
            return
        await itr.followup.send("Pinned!" if pinned else "Could not pin the song.")

    @app_commands.command()
    @app_commands.choices(game=game_choices(has_pins))
    @app_commands.autocomplete(artist=deck_autocomplete, song=song_autocomplete)
    async def pin_by_name(
        self, itr: Itr, game: app_commands.Choice[str], artist: str, song: str
    ) -> None:
        """Pin SSL song of the day using Artist/Album and Song

        Parameters
        ----------
        game: Game
        artist: Artist/Album
        song: Song
        """
        index = self.bot.indexes.get(game.value)
        code = parse_code(song)
        found = index.decks.songs.get(code) if index and code is not None else None
        if found is not None and found.deck_code != parse_code(artist):
            found = None
        await self._pin(itr, game.value, found.code if found else None)

    @app_commands.command()
    @app_commands.choices(game=game_choices(has_pins))
    @app_commands.autocomplete(id=song_id_autocomplete)
    async def pin_by_id(
        self, itr: Itr, game: app_commands.Choice[str], id: str
    ) -> None:
        """Pin SSL song of the day using Song ID

        Parameters
        ----------
        game: Game
        id: Song ID
        """
        await self._pin(itr, game.value, parse_code(id))


async def setup(bot: dBot) -> None:
    await bot.add_cog(SSLeague(bot))
