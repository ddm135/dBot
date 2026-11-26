"""Copy v0's JSON data into Postgres.

    uv run python -m scripts.import_v0 [--data-dir DIR]

Run it once, after the bot has synced the game data at least once (so the
song and deck names can be matched). It is safe to run again.
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from config import DEFAULT_DATA_DIR, PostgresSettings
from db import create_pool, migrate
from db.legacy import DateParser, DeckLookup, SongLookup, import_all
from games.data.storage import DataStore
from games.index import Index, build_index, find_deck_by_name
from games.registry import GAMES

logger = logging.getLogger(__name__)

V0_FILES = (
    "credentials",
    "word_pings",
    "roles",
    "ssleagues",
    "live_theme",
    "notify_bonus",
)
TABLES = ("MusicData", "ArtistData", "GroupData", "AlbumData", "LocaleData", "URLs")


def read_v0(directory: Path) -> dict[str, dict[str, Any]]:
    """The JSON files of v0 in ``directory`` by name; missing ones are skipped."""
    found: dict[str, dict[str, Any]] = {}
    for stem in V0_FILES:
        path = directory / f"{stem}.json"
        if path.exists():
            found[stem] = json.loads(path.read_text(encoding="utf-8"))
        else:
            logger.warning("%s is missing; skipping it.", path)
    return found


async def load_indexes(store: DataStore) -> dict[str, Index]:
    """The index of every game, for matching v0's names to decks."""
    indexes: dict[str, Index] = {}
    for game in GAMES.values():
        tables = await store.read_all(game.key, TABLES, pruned=False)
        if index := build_index(game, tables):
            indexes[game.key] = index
    return indexes


# Decks the old sheets know by a name they no longer carry.
RENAMED: dict[str, dict[str, str]] = {
    "SM": {
        "M&D": "K I M H E E C H U L & K I M J U N G M O",
        "NCT DREAM (Reload)": "NCT DREAM (DREAM AFTER DREAM)",
    },
    "EB": {"さくらしめじ": "sakurashimeji"},
}


def make_lookups(
    indexes: dict[str, Index],
) -> tuple[DeckLookup, SongLookup, DateParser]:
    """The functions that turn v0's artist names, song ids and dates into codes and dates."""

    def deck_of(game: str, artist: str) -> int | None:
        index = indexes.get(game)
        deck = find_deck_by_name(index, artist, RENAMED.get(game)) if index else None
        return deck.code if deck else None

    def deck_of_song(game: str, song: int) -> int | None:
        index = indexes.get(game)
        found = index.decks.songs.get(song) if index else None
        return found.deck_code if found else None

    def parse_date(game: str, text: str) -> date | None:
        try:
            return GAMES[game].parse_date(text).date()
        except KeyError, ValueError:
            return None

    return deck_of, deck_of_song, parse_date


async def main(argv: list[str]) -> int:
    """Import v0's JSON files from the data directory (``--data-dir``); returns the exit
    status.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)

    load_dotenv()
    postgres = PostgresSettings.from_env()  # the import needs no Discord token
    data_dir = args.data_dir or DEFAULT_DATA_DIR
    indexes = await load_indexes(DataStore(data_dir))
    if not indexes:
        logger.error("No game tables found in %s. Start the bot once first.", data_dir)
        return 1
    deck_of, deck_of_song, parse_date = make_lookups(indexes)

    pool = await create_pool(postgres)
    try:
        await migrate(pool)
        report = await import_all(
            pool,
            read_v0(data_dir),
            games=set(GAMES),
            deck_of=deck_of,
            deck_of_song=deck_of_song,
            parse_date=parse_date,
        )
    finally:
        await pool.close()

    for what, count in report.imported.items():
        print(f"{what}: {count}")
    for line in report.skipped:
        print(f"skipped: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
