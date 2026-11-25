"""What the game tables and the server's asset listing look like: table names, the fields that name files, the asset context."""

import copy
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any, Self

TABLE_NAMES = (
    "AlbumData",
    "ArtistData",
    "GroupData",
    "HiddenGameData",
    "LiveThemeData",
    "LocaleData",
    "MusicData",
    "ThemeData",
    "SeqData",
    "ThemeTypeData",
    "URLs",
    "WorldRecordData",
)


class AssetContextError(ValueError):
    """The data is not an asset context."""


@dataclass(frozen=True, slots=True)
class AssetFile:
    version: str
    url: str


@dataclass(frozen=True, slots=True)
class AssetContext:
    raw: Mapping[str, Any]

    @classmethod
    def from_json(cls, data: object) -> Self:
        """From what ``a.json`` holds: an object with a ``version`` and a ``context``."""
        if (
            not isinstance(data, Mapping)
            or "version" not in data
            or not isinstance(data.get("context"), Mapping)
        ):
            raise AssetContextError("The asset context has no version and/or context.")
        return cls(data)

    @property
    def version(self) -> str:
        return str(self.raw["version"])

    @property
    def context(self) -> Mapping[str, Any]:
        context: Mapping[str, Any] = self.raw["context"]
        return context

    def table_files(self) -> dict[str, AssetFile]:
        files = {}
        for name in TABLE_NAMES:
            entry = self.context.get(name)
            if (
                isinstance(entry, Mapping)
                and isinstance(entry.get("file"), str)
                and entry["file"]
            ):
                files[name] = AssetFile(str(entry.get("version", "")), entry["file"])
        return files

    def with_tables(self, replacements: Mapping[str, Mapping[str, Any] | None]) -> Self:
        raw = copy.deepcopy(dict(self.raw))
        context = raw["context"]
        for name, entry in replacements.items():
            if entry is None:
                context.pop(name, None)
            else:
                context[name] = copy.deepcopy(dict(entry))
        return type(self)(raw)


def tables_to_download(
    stored: AssetContext | None, current: AssetContext, on_disk: Collection[str]
) -> list[str]:
    refresh = stored is None or stored.version != current.version
    old = stored.table_files() if stored is not None else {}
    return [
        name
        for name, file in current.table_files().items()
        if refresh or old.get(name) != file or name not in on_disk
    ]


# The language columns of LocaleData the bot keeps and searches.
LOCALE_COLUMNS = ("enUS", "koKR", "jaJP", "jpJP", "zhTW")

# MusicData fields naming a song's chart, by difficulty.
DIFFICULTY_FIELDS = {"Easy": "seqEasy", "Normal": "seqNormal", "Hard": "seqHard"}

# Fields of each table that name a file (a catalog key, a URL, or a code in URLs).
FILE_FIELDS: dict[str, tuple[str, ...]] = {
    "GroupData": ("emblemImage",),
    "MusicData": ("album", "image", *DIFFICULTY_FIELDS.values()),
    "SeqData": ("seqPath",),
}

# Orders in which a game shows its names (the first language that has one).
ENGLISH_FIRST = ("enUS", "koKR", "jaJP", "jpJP")
KOREAN_FIRST = ("koKR", "enUS", "jaJP", "jpJP")
JAPANESE_FIRST = ("jaJP", "jpJP", "enUS", "koKR")
