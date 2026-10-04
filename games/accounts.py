"""The bot's own game accounts, with credentials kept in the database."""

import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Protocol

from .account import Account
from .auth import LoginCredentials
from .errors import LoginError
from .registry import GAMES
from .server import Server

logger = logging.getLogger(__name__)


class CredentialStore(Protocol):
    async def get(self, game: str) -> dict[str, Any] | None: ...

    async def save(self, game: str, fields: Mapping[str, Any]) -> None: ...


class Accounts:
    """One :class:`Account` per game that has stored credentials."""

    def __init__(self, server: Server, store: CredentialStore) -> None:
        self._server = server
        self._store = store
        self._accounts: dict[str, Account] = {}

    async def get(self, game_key: str) -> Account | None:
        """The account for a game, or None if it has no usable credentials."""
        if account := self._accounts.get(game_key):
            return account
        game = GAMES.get(game_key)
        fields = await self._store.get(game_key)
        if game is None or fields is None:
            return None
        try:
            credentials = LoginCredentials.from_mapping(fields)
        except LoginError:
            logger.warning("%s: The stored credentials are unusable.", game_key)
            return None
        if credentials.method_for(game) is None:
            logger.warning("%s: No login method fits the stored credentials.", game_key)
            return None
        account = Account(
            game,
            self._server,
            credentials,
            on_change=self._saver(game_key),
        )
        self._accounts[game_key] = account
        return account

    def _saver(self, game_key: str) -> Callable[[LoginCredentials], Awaitable[None]]:
        async def save(credentials: LoginCredentials) -> None:
            await self._store.save(game_key, credentials.fields)

        return save

    def forget(self, game_key: str) -> None:
        """Drop the cached account, e.g. after its credentials were replaced."""
        self._accounts.pop(game_key, None)
