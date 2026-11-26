"""Reading Unity Addressables binary catalogs (``catalog_*.bin``).

A catalog says which bundle holds each asset. The format is Unity's
``BinaryStorageBuffer``; only what the bot needs is decoded: the keys, and for
each key the internal ids and bundle URLs of its locations.
"""

import asyncio
import struct
from collections.abc import Iterable, Iterator, Sequence
from typing import NamedTuple, Protocol

NONE = 0xFFFFFFFF  # uint.MaxValue, used as "null" offset
UNICODE_FLAG = 0x80000000  # kUnicodeStringFlag
DYNAMIC_FLAG = 0x40000000  # kDynamicStringFlag
CLEAR_MASK = 0x3FFFFFFF  # kClearFlagsMask
CATALOG_VERSION = 2  # ContentCatalogData.kVersion


class HasKeys(Protocol):
    """A catalog that can list its keys."""

    def keys(self) -> Iterable[object]: ...


class HasBundleUrls(Protocol):
    """A catalog that can say which bundle files a key lives in."""

    def bundle_urls(self, key: object) -> list[str | None]: ...


class HasInternalIds(Protocol):
    """A catalog that can give the internal ids (asset paths) of a key."""

    def internal_ids(self, key: object) -> list[str | None]: ...


class CatalogError(ValueError):
    """The data is not a catalog this reader understands (or is corrupt)."""


class UnsupportedKeyError(CatalogError):
    """A key (or extra data) of a type this reader does not decode."""


class Location(NamedTuple):
    """One resource location: its key, internal id, provider and dependencies."""

    primary_key: str | None
    internal_id: str | None
    provider_id: str | None
    dependency_set: int
    extra_offset: int = NONE  # ObjectTypeData offset of the provider "extra data"
    type_id: int = NONE  # offset of the resource Type record


class BinaryStorageBuffer:
    """Read-only view over a BinaryStorageBuffer.

    Layout (all little-endian):
      * strings/arrays are length-prefixed: a u32 *byte* size sits at
        ``id - 4`` and the payload starts at ``id``.
      * structs are stored raw, referenced by their start offset.
      * a string id may carry flags: 0x80000000 = UTF-16, 0x40000000 = a
        "dynamic" string stored as a linked list of path segments.
    """

    def __init__(self, data: bytes) -> None:
        self.data = data
        self._strings: dict[tuple[object, ...], str | None] = {}
        self._locations: dict[int, Location] = {}

    # Integers
    def _check(self, offset: int, size: int) -> None:
        if offset < 0 or offset + size > len(self.data):
            raise CatalogError(
                f"Data offset {offset} is out of bounds of buffer with length {len(self.data)}."
            )

    def u32(self, offset: int) -> int:
        self._check(offset, 4)
        value: int = struct.unpack_from("<I", self.data, offset)[0]
        return value

    def u32_array(self, ident: int) -> Sequence[int] | None:
        """Offset lists or flat KeyData pairs."""
        if ident == NONE:
            return None
        size = self.u32(ident - 4)
        self._check(ident, size)
        return struct.unpack_from(f"<{size // 4}I", self.data, ident)

    # Strings
    def _ascii(self, raw: bytes) -> str:
        """.NET's Encoding.ASCII turns every byte > 0x7F into '?'."""
        return raw.decode("ascii", errors="replace").replace("\ufffd", "?")

    def _raw_string(self, offset: int, utf16: bool) -> str:
        length = self.u32(offset - 4)
        self._check(offset, length)
        raw = self.data[offset : offset + length]
        return raw.decode("utf-16-le", errors="replace") if utf16 else self._ascii(raw)

    def _auto_string(self, ident: int) -> str:
        if ident & UNICODE_FLAG:
            return self._raw_string(ident & CLEAR_MASK, True)
        return self._raw_string(ident, False)

    def read_string(self, ident: int, sep: str | None = None) -> str | None:
        """ReadString(id, sep).  With ``sep`` the id may be a dynamic string."""
        if ident == NONE:
            return None
        cache_key = (ident, sep)
        if cache_key in self._strings:
            return self._strings[cache_key]

        if sep and ident & DYNAMIC_FLAG:
            # Linked list; the head node is the LAST segment of the string.
            parts: list[str] = []
            node_id = ident
            hops = 0
            while node_id != NONE:
                node = node_id & CLEAR_MASK
                self._check(node, 8)
                string_id, node_id = struct.unpack_from("<II", self.data, node)
                parts.append(self._auto_string(string_id))
                hops += 1
                if hops > len(self.data) // 8 + 1:
                    raise CatalogError("Cyclic dynamic string chain.")
            value = sep.join(reversed(parts))
        else:
            value = self._auto_string(ident)

        self._strings[cache_key] = value
        return value

    # Objects
    def _type_name(self, type_id: int) -> str | None:
        """TypeSerializer: Data{assemblyId, classId}."""
        if type_id == NONE:
            return None
        self._check(type_id, 8)
        _assembly_id, class_id = struct.unpack_from("<II", self.data, type_id)
        return self.read_string(class_id, ".")

    def read_key(self, offset: int) -> object:
        """ReadObject(id): ObjectTypeData{typeId, objectId} then the value."""
        self._check(offset, 8)
        type_id, object_id = struct.unpack_from("<II", self.data, offset)
        type_name = self._type_name(type_id)
        if object_id == NONE:
            return None
        if type_name == "System.String":
            # ObjectToStringRemap { uint stringId; char separator; } (8 bytes)
            self._check(object_id, 6)
            string_id, sep_code = struct.unpack_from("<IH", self.data, object_id)
            return self.read_string(string_id, chr(sep_code) if sep_code else None)
        if type_name == "System.Int32":
            self._check(object_id, 4)
            return struct.unpack_from("<i", self.data, object_id)[0]
        if type_name == "System.Int64":
            self._check(object_id, 8)
            return struct.unpack_from("<q", self.data, object_id)[0]
        if type_name == "System.Boolean":
            self._check(object_id, 1)
            return bool(self.data[object_id])
        raise UnsupportedKeyError(
            f"Unsupported key type {type_name!r} at offset {offset}."
        )

    def location(self, offset: int) -> Location:
        """ResourceLocation.Serializer.Data (7 x 4 bytes)."""
        cached = self._locations.get(offset)
        if cached is not None:
            return cached
        self._check(offset, 28)
        (
            primary_off,
            internal_off,
            provider_off,
            dep_set,
            _dep_hash,
            extra_off,
            type_id,
        ) = struct.unpack_from("<IIIIiII", self.data, offset)
        loc = Location(
            primary_key=self.read_string(primary_off, "/"),
            # internal ids are read raw (WithInternalIdResolvingDisabled)
            internal_id=self.read_string(internal_off, "/"),
            provider_id=self.read_string(provider_off, "."),
            dependency_set=dep_set,
            extra_offset=extra_off,
            type_id=type_id,
        )
        self._locations[offset] = loc
        return loc


class BinaryCatalog:
    """A parsed catalog: the keys and where each is found.

    ``internal_ids`` gives the asset's own id and ``bundle_urls`` the bundles that
    contain it.
    """

    def __init__(self, data: bytes) -> None:
        if len(data) < 32:
            raise CatalogError("File is too small to be a binary catalog.")
        _magic, version, keys_offset = struct.unpack_from("<iiI", data, 0)
        if version != CATALOG_VERSION:
            raise CatalogError(
                f"Expected catalog data version {CATALOG_VERSION}, but file was written with version {version}."
            )
        self.buf = BinaryStorageBuffer(data)
        flat = self.buf.u32_array(keys_offset) or ()

        if len(flat) % 2:
            raise CatalogError("Key table is not made of (key, locations) pairs.")

        self._key_to_set: dict[tuple[type, object], int] = {}
        for key_offset, loc_set in zip(flat[0::2], flat[1::2]):
            key = self.buf.read_key(key_offset)
            slot = (type(key), key)
            if slot in self._key_to_set:
                raise CatalogError(f"Duplicate key in catalog: {key!r}.")
            self._key_to_set[slot] = loc_set

    def __len__(self) -> int:
        return len(self._key_to_set)

    def __contains__(self, key: object) -> bool:
        return (type(key), key) in self._key_to_set

    def keys(self) -> Iterator[object]:
        """Every key of the catalog."""
        return (key for _type, key in self._key_to_set)

    def internal_ids(self, key: object) -> list[str | None]:
        """Internal id of each location the key points at (raw, tokens unresolved).

        For an asset this is its own id (e.g. the name inside the bundle); for a
        bundle location it is the bundle URL/path.  A key may have several locations.
        """
        buf = self.buf
        return [
            buf.location(off).internal_id
            for off in buf.u32_array(self._key_to_set[(type(key), key)]) or ()
        ]

    def bundle_urls(self, key: object) -> list[str | None]:
        """Internal id of the bundle(s) that hold ``key`` (raw, tokens unresolved).

        An asset location has one bundle dependency; a bundle location (no
        dependencies) is its own bundle.  A key may have several locations.
        """

        buf = self.buf
        location_set = self._key_to_set[(type(key), key)]
        out: list[str | None] = []
        for off in buf.u32_array(location_set) or ():
            loc = buf.location(off)
            deps = buf.u32_array(loc.dependency_set)
            if deps:
                out.extend(buf.location(d).internal_id for d in deps)
            else:
                out.append(loc.internal_id)
        return out


async def load_catalog(data: bytes) -> BinaryCatalog:
    """Parse a catalog in a thread; it is big enough to hold up the event loop."""
    return await asyncio.to_thread(BinaryCatalog, data)
