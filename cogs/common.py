"""Pieces every command cog needs: game choices, autocomplete, lookups."""

from collections.abc import Callable
from operator import attrgetter
from typing import TYPE_CHECKING, Any, NamedTuple

import discord
from discord import app_commands

from games.data.decks import Deck
from games.index import Index
from games.models import Game
from games.registry import GAMES
from ui.images import Upload, prepare

if TYPE_CHECKING:
    from bot import dBot

type Itr = discord.Interaction[dBot]

NO_DATA = "There is no data for this game yet."


def game_choices(
    predicate: Callable[[Game], bool] = lambda game: True,
) -> list[app_commands.Choice[str]]:
    """The slash-command choices of the games that pass ``predicate``."""
    return [
        app_commands.Choice(name=game.name, value=game.key)
        for game in GAMES.values()
        if predicate(game)
    ]


has_pins = attrgetter("has_pins")
has_bonuses = attrgetter("has_bonuses")


def selected_game(itr: Itr) -> str | None:
    """The game key chosen so far in an interaction's ``game`` option, or None."""
    value = getattr(itr.namespace, "game", None)
    return value if isinstance(value, str) and value in GAMES else None


async def deck_autocomplete(itr: Itr, current: str) -> list[app_commands.Choice[str]]:
    """Autocomplete for an ``artist`` option: decks matching what was typed."""
    key = selected_game(itr)
    search = itr.client.search.game(key) if key else None
    if search is None:
        return []
    return [
        app_commands.Choice(name=hit.choice_name, value=str(hit.code))
        for hit in search.decks(current)
    ]


async def song_autocomplete(itr: Itr, current: str) -> list[app_commands.Choice[str]]:
    """Autocomplete for a ``song`` option: songs of the chosen artist matching what was
    typed.
    """
    key = selected_game(itr)
    search = itr.client.search.game(key) if key else None
    if search is None:
        return []
    deck = _int(getattr(itr.namespace, "artist", None))
    return [
        app_commands.Choice(name=hit.choice_name, value=str(hit.code))
        for hit in search.songs(current, deck)
    ]


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except TypeError, ValueError:
        return None


def parse_code(value: str | None) -> int | None:
    """An autocomplete value as a code, or None if it is not a number."""
    return _int(value)


def deck_of(index: Index, artist: str | None) -> Deck | None:
    """The deck (artist or album) an autocomplete value names."""
    return index.decks.decks.get(parse_code(artist) or -1)


class Chosen(NamedTuple):
    """A command's artist: the deck, its icon URL, and the images to attach."""

    deck: Deck
    icon: str | None
    uploads: list[Upload]


async def choose_artist(
    bot: dBot, itr: Itr, index: Index, artist: str, icon: str | None
) -> Chosen | None:
    """The deck and its emblem for a command's ``artist`` option.

    Tells the user and returns None if there is no such artist.
    """
    deck = deck_of(index, artist)
    if deck is None:
        await itr.followup.send("Artist not found.")
        return None
    emblem = await bot.images.emblem(index.game.key, deck.code)
    icon, uploads = prepare(emblem, icon, "emblem")
    return Chosen(deck, icon, uploads)


def icon_for(bot: dBot, key: str) -> str | None:
    """The game's own icon, shown when a deck has no emblem."""
    return bot.games.get(key).icon_url
