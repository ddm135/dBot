"""The errors the game clients raise on purpose, so callers can tell them from bugs.

``ServerError`` and its subclasses say whether trying again later may help.
"""

from collections.abc import Mapping
from typing import Any


class ServiceError(Exception):
    """Base class for everything the game clients raise on purpose."""


class ServerError(ServiceError):
    """Talking to a game server failed.

    ``retryable`` is true when trying again later may help (network trouble,
    server errors) and false when the server answered but refused or sent
    something unusable. ``__cause__`` carries the underlying exception.
    """

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class ManifestError(ServerError):
    """The game's manifest could not be fetched or understood."""


class LoginError(ServerError):
    """Logging in to a game failed.

    ``updates`` holds stored credential fields that changed before the failure
    (e.g. a rotated Dalcom refresh token). They must still be saved, or the
    account can no longer log in.
    """

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        updates: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, retryable=retryable)
        self.updates: dict[str, Any] = dict(updates or {})


class PlayStoreError(ServiceError):
    """The Google Play lookup failed."""


class DataSyncError(ServerError):
    """Game data (asset context, data tables, catalog) could not be synced."""
