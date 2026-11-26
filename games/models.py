"""What the registry says about a game, as plain data (:class:`Game` and its parts)."""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from types import MappingProxyType
from typing import Any
from zoneinfo import ZoneInfo


@dataclass(frozen=True, slots=True)
class PinTarget:
    """Where a game's song of the day is pinned in a guild: a channel and the role to
    mention.
    """

    channel_id: int
    role_id: int | None = None


# ``eq=False`` on classes holding mappings: they are singletons, so identity
# equality is what we want, and it keeps them hashable (a frozen dataclass
# hashes its fields, which fails for dicts).
@dataclass(frozen=True, slots=True, eq=False)
class ForwardConfig:
    """Where a game's maintenance and update notices are read, and the channels of
    each guild they are forwarded to.
    """

    maintenance_channel_id: int
    scheduled_channel_id: int | None = None
    targets: Mapping[int, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "targets", MappingProxyType(dict(self.targets)))

    def source_channel_id(self, *, scheduled: bool) -> int:
        """The channel the notices are read from: the scheduled-update one or the
        maintenance one.
        """
        if scheduled and self.scheduled_channel_id is not None:
            return self.scheduled_channel_id
        return self.maintenance_channel_id


@dataclass(frozen=True, slots=True)
class AppStoreLookup:
    """How to find a game in the App Store."""

    app_id: int
    country: str

    @property
    def params(self) -> dict[str, str]:
        return {"id": str(self.app_id), "country": self.country}


@dataclass(frozen=True, slots=True)
class CatalogPatterns:
    """How the files of a catalog-only game are recognised in its catalog: sounds, charts
    and borders.
    """

    sound: re.Pattern[str]
    seq: re.Pattern[str]
    border: re.Pattern[str]


@dataclass(frozen=True, slots=True)
class StringsConfig:
    """Names kept in a Unity Localization string table instead of the data tables."""

    collection: str  # the table collection, e.g. "ItemName"
    languages: tuple[str, ...]  # in order of preference
    album_key: str  # key of an album's title, with {code}
    group_key: str  # key of a group's name, with {code}
    song_key: str  # key of a song's title, with {code}
    theme_key: str = "Theme_{code}"  # key of a theme's name, with {code}


@dataclass(frozen=True, slots=True)
class GrpcConfig:
    """A game whose platform server speaks MagicOnion (gRPC with MessagePack)."""

    target: str  # host:port
    cdn_url: str  # where the asset bundle directories live
    secure: bool = True  # TLS; only tests use plain HTTP/2


# The locale text of each artist position (Vocal, Dance, Rhythm) in most games.
POSITION_LOCALE: Mapping[int, int] = MappingProxyType(
    {0: 51003001, 1: 51003002, 2: 51003003}
)


@dataclass(frozen=True, slots=True, eq=False)
class Game:
    """One game: its identity, how to reach it and what the bot does with it.

    Games are singletons from ``games.registry``, so they compare by identity.
    The optional parts say what a game has: a catalog, pins, forwarding, weekly
    seasons, a MagicOnion server, a string table, bonuses.
    """

    key: str
    name: str
    color: int
    timezone: ZoneInfo
    date_format: str

    package_name: str
    version_floor: str
    manifest_url: str

    album_decks: bool = False  # each album of AlbumData is a deck of its own
    album_image_key: str | None = None  # catalog key of an album's art, with {code}
    has_bonuses: bool = False  # the game's bonus calendar is worth showing
    base_score: int | None = None
    pins: Mapping[int, PinTarget] = field(default_factory=dict)  # by guild id
    forward: ForwardConfig | None = None

    first_season: date | None = None  # set for weekly world-record seasons
    app_store: AppStoreLookup | None = None
    icon_url: str | None = None  # set for games that are no longer listed
    # Where the catalog is. {version} is the resource version and {addressables}
    # the Addressables version, which the game's APK settings.json gives.
    catalog_url: str | None = None
    catalog_patterns: CatalogPatterns | None = None
    grpc: GrpcConfig | None = None
    strings: StringsConfig | None = None
    # Locale columns names are shown in, first one that has the text wins.
    languages: tuple[str, ...] = ("enUS", "koKR")
    # The locale text that names each artist position (``ArtistData.position``).
    position_locale: Mapping[int, int] = POSITION_LOCALE

    dalcom_authorization: str | None = None  # Basic auth for Dalcom ID login
    google_audience: str | None = None  # OAuth client id prefix for Google login

    def __post_init__(self) -> None:
        if not self.key or self.key != self.key.upper():
            raise ValueError(f"Game key must be upper case: {self.key!r}")
        if "{version}" not in self.manifest_url:
            raise ValueError(f"{self.key}: manifest URL has no {{version}} slot.")
        if self.catalog_url and not (
            "{version}" in self.catalog_url and "{addressables}" in self.catalog_url
        ):
            raise ValueError(
                f"{self.key}: catalog URL needs {{version}} and {{addressables}} slots."
            )
        if not 0 <= self.color <= 0xFFFFFF:
            raise ValueError(f"{self.key}: invalid colour {self.color:#x}.")
        # Make the mappings read-only (frozen only protects the attributes).
        object.__setattr__(self, "pins", MappingProxyType(dict(self.pins)))

    @property
    def is_unlisted(self) -> bool:
        return self.icon_url is not None

    @property
    def has_catalog(self) -> bool:
        return self.catalog_url is not None

    @property
    def is_catalog_only(self) -> bool:
        return self.catalog_patterns is not None

    @property
    def has_pins(self) -> bool:
        return bool(self.pins)

    @property
    def has_weekly_seasons(self) -> bool:
        return self.first_season is not None

    @property
    def has_quarterly_seasons(self) -> bool:
        return self.first_season is None and self.catalog_patterns is None

    def manifest_url_for(self, version: str) -> str:
        """The manifest address for a client version."""
        return self.manifest_url.format(version=version)

    def now(self) -> datetime:
        """The current time in the game's timezone."""
        return datetime.now(self.timezone)

    def format_date(self, value: datetime | date) -> str:
        """A date in the way the game's own sheets write it."""
        return value.strftime(self.date_format)

    def parse_date(self, text: str) -> datetime:
        """A date as the game writes it, in the game's timezone."""
        return datetime.strptime(text, self.date_format).replace(tzinfo=self.timezone)


type Entry = Mapping[str, Any]  # one row of a game table
type Tables = Mapping[str, Mapping[str, Entry]]  # the game tables, by name
