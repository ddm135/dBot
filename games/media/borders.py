"""The borders (theme frames) a game has, by the name they are announced under.

Two kinds of game. One lists its borders in the catalog by key
(``Image_ThemeType_<n>_R_Large``); only the borders of limited themes are
announced, as ``<n> - <name>`` with the name from the game's string table. The
other lists them in its tables (``ThemeTypeData`` and ``ThemeData``) and only
those of limited themes are announced; each is a normal ``_Large`` and, if the
theme has one, a ``_Zoom``.
"""

from collections.abc import Container
from itertools import count
from pathlib import PurePosixPath
from typing import Any, Protocol

from games.data.catalog import HasInternalIds, HasKeys
from games.data.strings import Strings, pick
from games.models import Game, Tables


class BorderCatalog(HasKeys, HasInternalIds, Protocol):
    """What the borders need of a catalog: its keys and their internal ids."""


def border_files(
    game: Game, tables: Tables, catalog: BorderCatalog, strings: Strings | None = None
) -> dict[str, str]:
    """``{announced name: catalog key}`` for every border of the game."""
    if game.catalog_patterns is not None:
        return _from_catalog(game, tables, strings or {}, catalog)
    if game.has_catalog:
        return _from_tables(tables)
    return {}


def _theme_names(game: Game, tables: Tables, strings: Strings) -> dict[str, str | None]:
    """``{border number: theme name}`` for the borders of limited themes.

    Only limited themes have borders worth announcing. The name is the game's
    own string (its table), else the theme's analytics name. A border several
    themes share under different names has none (None).
    """
    config = game.strings
    found: dict[str, set[str]] = {}
    for code, theme in tables.get("ThemeData", {}).items():
        number = str(theme.get("themeTypeCode") or "")
        if not number or not theme.get("limitedType"):
            continue
        name = (
            config
            and pick(strings, config.theme_key.format(code=code), config.languages)
            or str(theme.get("analyticsData") or "")
        ).strip()
        found.setdefault(number, set()).add(name)
    return {
        n: next(iter(names)) if len(names) == 1 and "" not in names else None
        for n, names in found.items()
    }


def _from_catalog(
    game: Game, tables: Tables, strings: Strings, catalog: BorderCatalog
) -> dict[str, str]:
    assert game.catalog_patterns is not None
    pattern = game.catalog_patterns.border
    names = _theme_names(game, tables, strings)
    found: dict[str, str] = {}
    for key in catalog.keys():  # noqa: SIM118 - a catalog, not a dict
        if not isinstance(key, str):
            continue
        match = pattern.fullmatch(key)
        if not match or match.group(1) not in names:
            continue  # not the border of a limited theme
        internal = next((i for i in catalog.internal_ids(key) if i), None)
        suffix = PurePosixPath(internal).suffix if internal else ""
        number = match.group(1)
        name = names[number]
        found[f"{number} - {name}{suffix}" if name else f"{number}{suffix}"] = key
    return found


def _from_tables(tables: Tables) -> dict[str, str]:
    locale = tables.get("LocaleData", {})
    # The first theme of each border number (looked up once, not scanned for).
    themes: dict[Any, Any] = {}
    for each in tables.get("ThemeData", {}).values():
        number = each.get("themeTypeCode")
        if isinstance(number, str | int | float):
            themes.setdefault(number, each)
    found: dict[str, str] = {}
    for border in tables.get("ThemeTypeData", {}).values():
        code = border.get("code")
        theme = themes.get(code) if isinstance(code, str | int | float) else None
        if not code or theme is None or not theme.get("limitedType"):
            continue
        entry = locale.get(str(theme.get("localeName")))
        name = entry.get("enUS") if entry else None
        grade = border.get("gradeR")
        if not name or not grade:
            continue
        key = PurePosixPath(grade)
        kinds = {"_Large": ""}
        if theme.get("nameImageZoom"):
            kinds["_Zoom"] = "z"
        for tail, mark in kinds.items():
            found[f"{code}{mark} - {name}{key.suffix}"] = str(
                key.with_stem(key.stem + tail)
            )
    return found


def old_name(name: str, taken: Container[str]) -> str:
    """ "515 - Ponytail.png" -> "515 (old) - Ponytail.png" ("(old 2)" if taken)."""
    number, dash, rest = name.partition(" - ")
    if not dash:
        number, dot, rest = name.partition(".")
        dash = dot
    for n in count(1):
        mark = " (old)" if n == 1 else f" (old {n})"
        old = f"{number}{mark}{dash}{rest}"
        if old not in taken:
            return old
    raise AssertionError  # unreachable
