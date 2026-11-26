"""Fills in the note counts and durations of every song.

For each song the three charts (Easy, Normal, Hard) are located through the
game's catalog, read from their bundles in place, and measured. The result is
written in v0's format (``MusicData/<game>.json``), which ``/info`` and the SSL
post read.

Bundles are downloaded once and kept; nothing is unpacked or deleted. The
bundles of charts that are already counted are downloaded too, if they are not
on disk, so every map is kept.
"""

import asyncio
import logging
import re
from collections import defaultdict
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol

from games.charts.seq import SeqError, parse_seq
from games.charts.song_stats import format_duration
from games.data.schema import DIFFICULTY_FIELDS
from games.media.bundles import (
    BuiltInBundle,
    BundleError,
    BundleStore,
    asset_name,
    bundle_name,
)
from games.models import Tables

logger = logging.getLogger(__name__)

DEFAULT_CONCURRENCY = 2  # bundles are decoded whole; the container has 1 GB
FLUSH_EVERY = 50  # bundles between saves, so a long first run is not lost

type Stored = dict[str, Any]


class Catalog(Protocol):
    """What the sync needs of a catalog: keys, ids and bundle URLs."""

    def bundle_urls(self, key: object) -> list[str | None]: ...
    def internal_ids(self, key: object) -> list[str | None]: ...

    def keys(self) -> Iterable[object]: ...


@dataclass(frozen=True, slots=True)
class SeqRef:
    """A song's chart of one difficulty: a catalog key, or a code in the URLs table."""

    song: str
    level: str
    ref: int | str  # a catalog key, or a code in the URLs table


@dataclass(frozen=True, slots=True)
class Source:
    """Where a chart is: its URL, the bundle and asset inside it, and the key that tells
    whether it changed.
    """

    ref: SeqRef
    url: str
    key: str  # what is stored to recognise an unchanged chart
    dependency: str | None  # the bundle's file name; None for a plain file
    asset: str | None  # the asset inside the bundle; None for a plain file
    asset_id: str | None = None  # the catalog's id for it, which names one asset


@dataclass(slots=True)
class SyncResult:
    """What a sync of charts did, counted by outcome, and the songs it touched."""

    updated: int = 0  # charts measured
    unchanged: int = 0
    built_in: int = 0  # in the game's APK, so not downloadable
    missing: int = 0  # not in the catalog or the URL table
    failed: int = 0
    downloaded: int = 0  # bundles of charts already counted, fetched to keep
    songs: set[str] = field(default_factory=set)


def collect_refs(tables: Tables) -> list[SeqRef]:
    """Every chart reference in the tables.

    Games with a ``SeqData`` table list charts there; the others put the three
    references on the song.
    """
    refs: list[SeqRef] = []
    seq_data = tables.get("SeqData")
    if seq_data:
        for entry in seq_data.values():
            path = entry.get("seqPath")
            if path is not None and entry.get("linkedMusic") is not None:
                refs.append(
                    SeqRef(str(entry["linkedMusic"]), str(entry.get("seqLevel")), path)
                )
        return refs
    for code, song in tables.get("MusicData", {}).items():
        for level, name in DIFFICULTY_FIELDS.items():
            ref = song.get(name)
            if isinstance(ref, int | str) and not isinstance(ref, bool) and ref != "":
                refs.append(SeqRef(str(code), level, ref))
    return refs


def catalog_refs(
    tables: Tables, catalog: Catalog, pattern: re.Pattern[str]
) -> list[SeqRef]:
    """The charts of a game whose tables do not name them, found by catalog key.

    The key carries the song and the level: ``bytes_notes_<song>_<level>``.
    Songs the tables do not know are left out.
    """
    known = tables.get("MusicData", {})
    refs = []
    for key in catalog.keys():  # noqa: SIM118 - a catalog, not a dict
        if not isinstance(key, str):
            continue
        match = pattern.fullmatch(key)
        if match and match.group(1) in known:
            refs.append(SeqRef(match.group(1), match.group(2).capitalize(), key))
    return refs


def resolve(ref: SeqRef, tables: Tables, catalog: Catalog | None) -> Source | None:
    """Where a chart lives, or None if it cannot be located."""
    if isinstance(ref.ref, int):
        url = (tables.get("URLs", {}).get(str(ref.ref)) or {}).get("url")
        if not isinstance(url, str):
            return None
        return Source(ref, url, url, None, None)
    if ref.ref.startswith(("http://", "https://")):  # some games store the URL itself
        return Source(ref, ref.ref, ref.ref, None, None)
    if catalog is None:
        return None
    try:
        urls = [u for u in catalog.bundle_urls(ref.ref) if u]
    except KeyError:
        return None
    if not urls:
        return None
    ids = [i for i in catalog.internal_ids(ref.ref) if i]
    return Source(
        ref,
        urls[0],
        ref.ref,
        bundle_name(urls[0]),
        asset_name(ref.ref),
        ids[0] if ids else None,
    )


def is_current(stored: Stored, source: Source) -> bool:
    """Whether a stored chart was made from this source (its key is unchanged)."""
    entry = stored.get(source.ref.song, {}).get("seq", {}).get(source.ref.level)
    return (
        isinstance(entry, dict)
        and isinstance(entry.get("count"), int)
        and entry.get("key") == source.key
        and entry.get("dependency") == source.dependency
    )


def apply(stored: Stored, source: Source, count: int, seconds: float) -> None:
    """Store a chart's measurement in the stats of its song."""
    song = stored.setdefault(source.ref.song, {})
    song.setdefault("seq", {})[source.ref.level] = {
        "count": count,
        "duration": seconds,
        "key": source.key,
        "dependency": source.dependency,
    }


def refresh_duration(song: Stored) -> None:
    """The song's length: its shortest chart, rounded to the second."""
    lengths = [
        info["duration"]
        for info in song.get("seq", {}).values()
        if isinstance(info.get("duration"), int | float)
    ]
    if lengths:
        song["duration"] = format_duration(min(lengths))


async def _measure(
    game_key: str, url: str, sources: list[Source], bundles: BundleStore
) -> dict[Source, tuple[int, float] | BundleError | SeqError]:
    """Measure every chart that lives at one URL."""
    results: dict[Source, tuple[int, float] | BundleError | SeqError] = {}
    plain = [s for s in sources if s.asset is None]
    inside = [s for s in sources if s.asset is not None]
    try:
        contents: dict[str, bytes] = {}
        if inside:
            names = {s.asset for s in inside if s.asset}
            ids = {s.asset_id for s in inside if s.asset_id}
            contents = await bundles.read(game_key, url, names, ids)
        for source in inside:
            data = contents.get(source.asset_id or "") or contents.get(
                source.asset or ""
            )
            if data is None:
                results[source] = BundleError(
                    f"{source.asset} is not in {source.dependency}"
                )
                continue
            results[source] = _parse(data)
        for source in plain:
            path = await bundles.fetch(game_key, url, plain=True)
            results[source] = _parse(await asyncio.to_thread(path.read_bytes))
    except BundleError as exc:
        for source in sources:
            results.setdefault(source, exc)
    return results


def _parse(data: bytes) -> tuple[int, float] | SeqError:
    try:
        stats = parse_seq(data)
    except SeqError as exc:
        return exc
    return stats.count, stats.seconds


def _classify(
    game_key: str,
    tables: Tables,
    catalog: Catalog | None,
    stored: Stored,
    known_bad: set[str],
    seq_pattern: re.Pattern[str] | None,
    result: SyncResult,
) -> tuple[dict[str, list[Source]], set[tuple[str, bool]]]:
    """Sort every chart into: to measure (by bundle), kept as it is, or missing."""
    by_url: dict[str, list[Source]] = defaultdict(list)
    keep: set[tuple[str, bool]] = set()  # (url, plain) of charts not measured
    refs = (
        catalog_refs(tables, catalog, seq_pattern)
        if seq_pattern is not None and catalog is not None
        else collect_refs(tables)
    )
    for ref in refs:
        source = resolve(ref, tables, catalog)
        if source is None:
            result.missing += 1
        elif is_current(stored, source):
            result.unchanged += 1
            keep.add((source.url, source.asset is None))
        elif f"{game_key}:{source.key}" in known_bad:
            result.failed += 1
            keep.add((source.url, source.asset is None))
        else:
            by_url[source.url].append(source)
    return by_url, keep


def _absent(
    game_key: str, bundles: BundleStore, keep: set[tuple[str, bool]]
) -> list[tuple[str, bool]]:
    """The kept charts whose bundle is not on disk (sorted, so runs are alike)."""
    present = bundles.on_disk(game_key)
    return [(url, plain) for url, plain in sorted(keep) if not present(url, plain)]


async def sync_seq_stats(
    game_key: str,
    tables: Tables,
    catalog: Catalog | None,
    bundles: BundleStore,
    stored: Stored,
    save: Callable[[], Awaitable[None]],
    *,
    concurrency: int = DEFAULT_CONCURRENCY,
    flush_every: int = FLUSH_EVERY,
    known_bad: set[str] | None = None,
    seq_pattern: re.Pattern[str] | None = None,
) -> SyncResult:
    """Measure the charts that are new or changed, updating ``stored`` in place.

    ``save`` is called now and then and at the end. ``known_bad`` collects
    charts that cannot be read, so they are not retried (and logged) every run.
    """
    result = SyncResult()
    known_bad = known_bad if known_bad is not None else set()
    # Thousands of charts, each looked up in the catalog: seconds of work that
    # would hold the event loop (and the lease with it), so it runs in a thread.
    by_url, keep = await asyncio.to_thread(
        _classify, game_key, tables, catalog, stored, known_bad, seq_pattern, result
    )
    # Also in a thread: a path is worked out and checked for every kept chart.
    absent = await asyncio.to_thread(_absent, game_key, bundles, keep)

    semaphore = asyncio.Semaphore(concurrency)
    done = 0
    lock = asyncio.Lock()

    async def work(url: str, sources: list[Source]) -> None:
        nonlocal done
        async with semaphore:
            outcomes = await _measure(game_key, url, sources, bundles)
        async with lock:
            for source, outcome in outcomes.items():
                if isinstance(outcome, tuple):
                    apply(stored, source, *outcome)
                    result.updated += 1
                    result.songs.add(source.ref.song)
                elif isinstance(outcome, BuiltInBundle):
                    result.built_in += 1
                else:
                    result.failed += 1
                    known_bad.add(f"{game_key}:{source.key}")
                    logger.warning("%s: chart %s: %s", game_key, source.key, outcome)
            done += 1
            if flush_every and done % flush_every == 0:
                for song in result.songs:
                    refresh_duration(stored[song])
                await save()

    async def keep_bundle(url: str, plain: bool) -> None:
        async with semaphore:
            try:
                await bundles.fetch(game_key, url, plain=plain)
            except BuiltInBundle:
                return
            except BundleError as exc:
                logger.warning("%s: bundle %s: %s", game_key, url, exc)
                return
        result.downloaded += 1

    await asyncio.gather(
        *(work(url, sources) for url, sources in by_url.items()),
        *(keep_bundle(url, plain) for url, plain in absent),
    )
    for song in result.songs:
        refresh_duration(stored[song])
    if result.updated:
        await save()
    return result
