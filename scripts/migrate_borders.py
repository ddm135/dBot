"""Brings the border files in Google Drive up to date with how the bot keeps them.

    uv run python -m scripts.migrate_borders [--apply] [--stamp-unknown] [--game KEY]

Without ``--apply`` it only reports. Per game it looks at every border the game
has and the file Drive holds for it:

* kept under its number alone ("12.png") -> renamed to "12 - Name.png";
* with the old long source recorded -> the short fingerprint is recorded instead
  (the same border, in the form Drive's 124-byte property limit allows);
* with no source (uploaded before sources were recorded) -> left alone, unless
  ``--stamp-unknown``, which records the game's current source for it. That says
  "this file is the border as it is now"; use it only if that is true;
* with a different source -> the game has republished it; the bot will upload
  the new one itself, so this is only reported.

The last line says how many files still need the bot's compatibility handling
(number-only names, long or missing sources). At 0, that handling can be removed.
"""

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from dotenv import load_dotenv

from config import Settings
from games.data.catalog import BinaryCatalog, CatalogError, load_catalog
from games.data.storage import DataStore
from games.data.strings import Strings, load_strings
from games.media.borders import border_files
from games.media.bundles import BundleStore
from games.media.drive import Drive, StoredFile, fingerprint
from games.models import Game, Tables
from games.registry import GAMES
from tasks.borders import _source

logger = logging.getLogger("migrate_borders")


@dataclass(slots=True)
class Plan:
    """What would bring the Drive folder in line with the borders: renames, fingerprints to
    add, and counts of the rest.
    """

    renames: list[tuple[str, str, str]] = field(default_factory=list)  # id, old, new
    to_fingerprint: list[tuple[str, str, str]] = field(
        default_factory=list
    )  # id, name, value
    unknown: list[tuple[str, str, str]] = field(default_factory=list)  # id, name, value
    current: int = 0
    republished: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)  # wanted, not in Drive at all
    extra: int = 0  # files in Drive that are not a border the game has

    @property
    def pending(self) -> int:
        """Files that still rely on the bot's compatibility handling."""
        return len(self.renames) + len(self.to_fingerprint) + len(self.unknown)


def plan(
    wanted: dict[str, str], sources: dict[str, str], have: dict[str, StoredFile]
) -> Plan:
    """What would bring ``have`` (the Drive folder) in line with ``wanted``."""
    result = Plan()
    files = dict(have)
    for name in wanted:  # a number alone becomes "<number> - <name>"
        number, dash, rest = name.partition(" - ")
        if not dash or name in files:
            continue
        old = f"{number}{Path(rest).suffix}"
        if old in files:
            result.renames.append((files[old].id, old, name))
            files[name] = files.pop(old)
    for name in wanted:
        stored = files.get(name)
        if stored is None:
            result.missing.append(name)
        elif stored.source is None:
            result.unknown.append((stored.id, name, fingerprint(sources[name])))
        elif stored.source == fingerprint(sources[name]):
            result.current += 1
        elif stored.source == sources[name]:
            result.to_fingerprint.append((stored.id, name, fingerprint(sources[name])))
        else:
            result.republished.append(name)
    result.extra = len([n for n in files if n not in wanted])
    return result


async def _load(
    game: Game, data_dir: Path, bundles: BundleStore
) -> tuple[Tables, BinaryCatalog, Strings] | None:
    store = DataStore(data_dir)
    tables = await store.read_all(game.key)
    catalog = None
    for path in sorted(store.catalog_dir(game.key).glob("*.bin")):
        try:
            catalog = await load_catalog(path.read_bytes())
        except CatalogError:
            continue
    if catalog is None:
        return None
    strings = {}
    if game.strings is not None:
        strings = await load_strings(game.key, catalog, bundles, game.strings)
    return tables, catalog, strings


async def _apply(folder: Drive, plan_: Plan, *, stamp_unknown: bool) -> None:
    for file_id, _, new in plan_.renames:
        await folder.rename(file_id, new)
    for file_id, _, value in plan_.to_fingerprint:
        await folder.set_source(file_id, value)
    if stamp_unknown:
        for file_id, _, value in plan_.unknown:
            await folder.set_source(file_id, value)


async def run(args: argparse.Namespace) -> int:
    """Check every game's Drive folder against its borders; with ``--apply``,
    rename and stamp the files.
    """
    settings = Settings.from_env()
    google = settings.google
    if not google.credentials_file.is_file():
        print(f"No Google credentials at {google.credentials_file}.")
        return 1
    folder = Drive.from_service_account(
        google.border_folder_id, google.credentials_file
    )
    pending = 0
    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        bundles = BundleStore(settings.data_dir, client)
        for game in GAMES.values():
            if args.game and game.key != args.game:
                continue
            loaded = await _load(game, settings.data_dir, bundles)
            if loaded is None:
                continue
            tables, catalog, strings = loaded
            wanted = border_files(game, tables, catalog, strings)
            if not wanted:
                continue
            sources = {name: _source(catalog, key) for name, key in wanted.items()}
            folder_id = await folder.game_folder(game.name)
            plan_ = plan(wanted, sources, await folder.files(folder_id))
            _report(game, plan_, applied=args.apply, stamped=args.stamp_unknown)
            if args.apply:
                await _apply(folder, plan_, stamp_unknown=args.stamp_unknown)
                remaining = 0 if args.stamp_unknown else len(plan_.unknown)
            else:
                remaining = plan_.pending
            pending += remaining
    print(
        f"\n{pending} file(s) still rely on the bot's compatibility handling."
        + (" It can be removed." if pending == 0 else "")
    )
    return 0


def _report(game: Game, plan_: Plan, *, applied: bool, stamped: bool) -> None:
    verb = "Renamed" if applied else "Would rename"
    print(f"\n{game.name}: {plan_.current} current, {plan_.extra} other files")
    for _, old, new in plan_.renames:
        print(f"  {verb}: {old} -> {new}")
    for _, name, _ in plan_.to_fingerprint:
        print(f"  {'Shortened' if applied else 'Would shorten'} the source of {name}")
    for _, name, _ in plan_.unknown:
        done = applied and stamped
        print(f"  {'Stamped' if done else 'No source (left alone)'}: {name}")
    for name in plan_.republished:
        print(f"  Republished by the game (the bot will upload it): {name}")
    for name in plan_.missing:
        print(f"  Not in Drive yet (the bot will upload it): {name}")


def main() -> None:
    """Parse the arguments and run."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="make the changes")
    parser.add_argument(
        "--stamp-unknown",
        action="store_true",
        help="with --apply, record the current source on files that have none",
    )
    parser.add_argument("--game", help="only this game's key, e.g. BL")
    args = parser.parse_args()
    load_dotenv()
    logging.basicConfig(level=logging.WARNING)
    try:
        sys.exit(asyncio.run(run(args)))
    except RuntimeError as exc:
        sys.exit(f"Configuration error:\n{exc}")


if __name__ == "__main__":
    main()
