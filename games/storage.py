import asyncio
import hashlib
import json
import logging
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .assets import TABLE_NAMES, AssetContext, AssetContextError
from .fields import FILE_FIELDS, LOCALE_COLUMNS

logger = logging.getLogger(__name__)

type Table = dict[str, dict[str, Any]]

# What the bot reads of the biggest tables. The files keep everything; only
# the copy held in memory is cut down to these fields (all the languages and
# the bookkeeping columns of every game would otherwise cost hundreds of MB).
KEPT_FIELDS: dict[str, frozenset[str]] = {
    "LocaleData": frozenset(LOCALE_COLUMNS),
    "URLs": frozenset({"url"}),
}


# Fields of the other tables that hold a code of a table the bot only reads by
# code. Names are looked up in LocaleData; files (emblems, album art, charts)
# in URLs, for the games that name them by code and not by catalog key or URL.
REFERENCE_FIELDS: dict[str, tuple[str, ...]] = {
    "LocaleData": ("localeName", "localeDisplayGroupName", "albumName"),
    "URLs": tuple(dict.fromkeys(f for fields in FILE_FIELDS.values() for f in fields)),
}


def prune_referenced(name: str, tables: Mapping[str, Table]) -> Table | None:
    """Only the entries of ``name`` that the other tables refer to.

    LocaleData holds every string of the game (items, menus, ...), of which the
    bot reads the few names that songs, groups and themes point at. URLs holds
    every file, and is read by code from a few fields; a game whose tables name
    files by catalog key or URL refers to none, and keeps none.
    """
    table = tables.get(name)
    fields = REFERENCE_FIELDS.get(name)
    if table is None or fields is None:
        return table
    wanted: set[str] = set()
    for other, rows in tables.items():
        if other == name:
            continue
        for entry in rows.values():
            for field in fields:
                value = entry.get(field)
                if (
                    value is not None
                    and not isinstance(value, bool)
                    and (isinstance(value, int) or name == "LocaleData")
                ):
                    wanted.add(str(value))
    return {code: entry for code, entry in table.items() if code in wanted}


def _trimmed(name: str, data: Any) -> Table | None:
    """A table as the bot keeps it, from what its file holds (None if unusable)."""
    table: Table | None = None
    if isinstance(data, dict):
        table = {str(key): value for key, value in data.items()}
    elif isinstance(data, list):
        try:
            table = {str(item["code"]): item for item in data}
        except KeyError, TypeError:
            pass
    return slim(name, table) if table is not None else None


def slim(name: str, table: Table) -> Table:
    """``table`` as the bot keeps it in memory."""
    keep = KEPT_FIELDS.get(name)
    if keep is None:
        return table
    return {
        code: {field: value for field, value in entry.items() if field in keep}
        for code, entry in table.items()
    }


def _read_json(path: Path) -> Any | None:
    try:
        text = path.read_text(encoding="utf-8-sig")  # tolerates a byte order mark
    except FileNotFoundError:
        return None
    except UnicodeDecodeError:
        logger.warning("%s is not valid text; ignoring it.", path)
        return None
    try:
        return json.loads(text)
    except ValueError:
        logger.warning("%s is not valid JSON; ignoring it.", path)
        return None


def _write_json(path: Path, data: Any, indent: int | None = 4) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(
            json.dumps(data, indent=indent, ensure_ascii=False), encoding="utf-8"
        )
        os.replace(temporary, path)  # readers never see a half-written file
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _signature(directory: Path) -> str:
    """Stands for the table files as they are now, and for how they are cut down.

    A kept table (see ``DataStore.read_kept``) is only good while none of the
    files it was made from has changed, nor the fields it keeps.
    """
    parts: list[object] = [sorted(KEPT_FIELDS.items(), key=str), REFERENCE_FIELDS]
    for name in sorted(TABLE_NAMES):
        try:
            status = (directory / f"{name}.json").stat()
        except FileNotFoundError:
            continue
        parts.append((name, status.st_size, status.st_mtime_ns))
    return hashlib.sha256(repr(parts).encode()).hexdigest()


def _read_kept(path: Path, signature: str) -> Table | None:
    data = _read_json(path)
    if not isinstance(data, dict) or data.get("signature") != signature:
        return None
    table = data.get("table")
    return table if isinstance(table, dict) else None


def _present_tables(directory: Path) -> set[str]:
    return {name for name in TABLE_NAMES if (directory / f"{name}.json").is_file()}


class DataStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _game_dir(self, game_key: str) -> Path:
        return self.root / "dalcom" / game_key

    def assets_path(self, game_key: str) -> Path:
        return self._game_dir(game_key) / "a.json"

    def table_path(self, game_key: str, name: str) -> Path:
        return self._game_dir(game_key) / f"{name}.json"

    def catalog_dir(self, game_key: str) -> Path:
        return self.root / "catalogs" / game_key

    async def read_json(self, path: Path) -> Any | None:
        return await asyncio.to_thread(_read_json, path)

    async def write_json(self, path: Path, data: Any) -> None:
        await asyncio.to_thread(_write_json, path, data)

    async def read_assets(self, game_key: str) -> AssetContext | None:
        data = await self.read_json(self.assets_path(game_key))
        if data is None:
            return None
        try:
            return AssetContext.from_json(data)
        except AssetContextError:
            logger.warning("%s: the stored a.json is not an asset context.", game_key)
            return None

    async def write_assets(self, game_key: str, index: AssetContext) -> None:
        await self.write_json(self.assets_path(game_key), index.raw)

    async def present_tables(self, game_key: str) -> set[str]:
        return await asyncio.to_thread(_present_tables, self._game_dir(game_key))

    def kept_path(self, game_key: str, name: str) -> Path:
        return self._game_dir(game_key) / "slim" / f"{name}.json"

    async def signature(self, game_key: str) -> str:
        return await asyncio.to_thread(_signature, self._game_dir(game_key))

    async def read_kept(self, game_key: str, name: str) -> Table | None:
        """The big table ``name`` as the bot keeps it, if it was saved from the
        files that are there now. Parsing it costs next to nothing, where the
        full file is seconds of CPU on a slow host."""
        signature = await self.signature(game_key)
        return await asyncio.to_thread(
            _read_kept, self.kept_path(game_key, name), signature
        )

    async def write_kept(self, game_key: str, name: str, table: Table) -> None:
        signature = await self.signature(game_key)
        data = {"signature": signature, "table": table}
        await asyncio.to_thread(_write_json, self.kept_path(game_key, name), data, None)

    async def read_table(self, game_key: str, name: str) -> Table | None:
        data = await self.read_json(self.table_path(game_key, name))
        # Keyed and trimmed in a thread: a big table is seconds of work.
        return await asyncio.to_thread(_trimmed, name, data)

    async def write_table(self, game_key: str, name: str, table: Table) -> None:
        await self.write_json(self.table_path(game_key, name), table)
