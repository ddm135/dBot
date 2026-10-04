"""Text from Unity Localization string tables, read from the kept bundles.

A game that does not put every name in its data tables keeps some in a Unity
string table. The catalog says where: the table of each language is the key
``<collection>_<language>`` and the ids' key names are in the key
``Assets/Localization/Tables/<collection> Shared Data.asset``. Nothing here
knows a bundle's file name; they are looked up in the catalog and downloaded
like any other bundle, and read in place.
"""

import asyncio
import logging
from collections.abc import Mapping
from typing import Any, Protocol

from .bundles import BuiltInBundle, BundleError, BundleStore, Source, open_environment
from .models import StringsConfig

logger = logging.getLogger(__name__)

type Strings = Mapping[str, Mapping[str, str]]  # key -> {language: text}


class Catalog(Protocol):
    def bundle_urls(self, key: object) -> list[str | None]: ...


def shared_data_key(collection: str) -> str:
    return f"Assets/Localization/Tables/{collection} Shared Data.asset"


def table_key(collection: str, language: str) -> str:
    return f"{collection}_{language}"


def _behaviours(source: Source) -> list[dict[str, Any]]:
    try:
        with open_environment(source) as environment:
            return [
                obj.read_typetree()
                for obj in environment.objects
                if obj.type.name == "MonoBehaviour"
            ]
    except Exception as exc:  # UnityPy raises many kinds of errors
        raise BundleError(f"Could not read a string table: {exc!r}") from exc


def read_key_names(source: Source, collection: str) -> dict[int, str]:
    """The key name of every id of a collection (from its shared data)."""
    names: dict[int, str] = {}
    for item in _behaviours(source):
        if item.get("m_TableCollectionName") == collection:
            for entry in item.get("m_Entries", ()):
                names[entry["m_Id"]] = entry["m_Key"]
    return names


def read_texts(source: Source, name: str) -> dict[int, str]:
    """The text of every id of the table called ``name`` (``ItemName_en``)."""
    for item in _behaviours(source):
        if item.get("m_Name") == name:
            return {e["m_Id"]: e["m_Localized"] for e in item.get("m_TableData", ())}
    return {}


async def _open(
    bundles: BundleStore, game_key: str, catalog: Catalog, key: str
) -> Source | None:
    try:
        urls = [u for u in catalog.bundle_urls(key) if u]
    except KeyError:
        return None
    if not urls:
        return None
    try:
        return await bundles.open(game_key, urls[0])
    except BuiltInBundle:
        logger.warning("%s: %s is built in and not downloadable.", game_key, key)
        return None


async def load_strings(
    game_key: str, catalog: Catalog, bundles: BundleStore, config: StringsConfig
) -> dict[str, dict[str, str]]:
    """Every string of the collection by key name, in each configured language.

    Nothing is returned if the catalog does not have the collection.
    """
    shared = await _open(bundles, game_key, catalog, shared_data_key(config.collection))
    if shared is None:
        return {}
    names = await asyncio.to_thread(read_key_names, shared, config.collection)
    strings: dict[str, dict[str, str]] = {}
    for language in config.languages:
        name = table_key(config.collection, language)
        source = await _open(bundles, game_key, catalog, name)
        if source is None:
            continue
        texts = await asyncio.to_thread(read_texts, source, name)
        for ident, text in texts.items():
            key = names.get(ident)
            if key and text:
                strings.setdefault(key, {})[language] = text
    return strings


def pick(strings: Strings, key: str, languages: tuple[str, ...]) -> str | None:
    """The text of a key in the first language that has it."""
    texts = strings.get(key)
    if not texts:
        return None
    return next((texts[lang] for lang in languages if texts.get(lang)), None)
