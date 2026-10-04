"""Where the bot's memory goes: what each game's data costs once loaded.

    uv run python -m scripts.memory_report [--data-dir DIR]

Loads every game's tables, catalog and index the way the bot does, without
Discord or a database, and prints what each one holds (Python objects, as
tracemalloc counts them), largest first, then the process size.
"""

import argparse
import asyncio
import gc
import sys
import tracemalloc
from pathlib import Path

from config import DEFAULT_DATA_DIR
from games.assets import TABLE_NAMES
from games.catalog import CatalogError, load_catalog
from games.index import build_index
from games.registry import GAMES
from games.storage import REFERENCE_FIELDS, DataStore, prune_referenced

MB = 1024 * 1024


def peak_size() -> float | None:
    """The process's peak size in MB, where the platform can say."""
    try:
        import resource
    except ImportError:  # Windows has no resource module
        pass
    else:
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    return None


def traced() -> int:
    gc.collect()
    return tracemalloc.get_traced_memory()[0]


def deep_size(value: object, seen: set[int] | None = None) -> int:
    """Bytes of a table's dicts, lists and values (shared strings counted once)."""
    seen = set() if seen is None else seen
    if id(value) in seen:
        return 0
    seen.add(id(value))
    size = sys.getsizeof(value)
    if isinstance(value, dict):
        size += sum(deep_size(k, seen) + deep_size(v, seen) for k, v in value.items())
    elif isinstance(value, list | tuple):
        size += sum(deep_size(item, seen) for item in value)
    return size


async def report(data_dir: Path) -> None:
    store = DataStore(data_dir)
    rows: list[tuple[float, str]] = []
    tracemalloc.start()
    keep: list[object] = []  # everything stays loaded, as in the bot
    start = traced()

    for game in GAMES.values():
        tables = {}
        for name in TABLE_NAMES:
            table = await store.read_table(game.key, name)
            if table is not None:
                tables[name] = table
        for name in REFERENCE_FIELDS:
            if (pruned := prune_referenced(name, tables)) is not None:
                tables[name] = pruned  # the full one is let go, as in the bot
        keep.append(tables)
        gc.collect()
        for name, table in tables.items():
            rows.append((deep_size(table) / MB, f"{game.key} table {name}"))

        before = traced()
        for path in sorted(store.catalog_dir(game.key).glob("*.bin")):
            try:
                catalog = await load_catalog(path.read_bytes())
            except CatalogError:
                continue
            keep.append(catalog)
            rows.append(((traced() - before) / MB, f"{game.key} catalog {path.name}"))
            before = traced()

        before = traced()
        try:
            index = build_index(game, tables)
        except Exception as error:  # noqa: BLE001 - report what can be measured
            print(f"{game.key}: no index ({error!r})")
            continue
        keep.append(index)
        rows.append(((traced() - before) / MB, f"{game.key} index (beyond tables)"))

    rows.sort(reverse=True)
    for size, label in rows[:25]:
        print(f"{size:8.1f} MB  {label}")
    print(
        f"\n{(traced() - start) / MB:8.1f} MB  held in all (Python objects, tracemalloc)"
    )
    peak = peak_size()
    if peak is not None:
        print(f"{peak:8.1f} MB  size of this process")
    tables_total = sum(s for s, label in rows if " table " in label)
    catalogs_total = sum(s for s, label in rows if " catalog " in label)
    print(
        f"{tables_total:8.1f} MB  of that is tables, {catalogs_total:.1f} MB catalogs"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    asyncio.run(report(parser.parse_args().data_dir))


if __name__ == "__main__":
    main()
