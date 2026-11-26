"""The bot's own game accounts: a logged-in account, the accounts kept in the database, and what only an account can ask (the Star League song of the day)."""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Protocol

from games.api.auth import LoginCredentials, Session
from games.api.manifest import Manifest
from games.api.server import Server
from games.errors import LoginError, ServerError
from games.models import Game
from games.registry import GAMES

logger = logging.getLogger(__name__)

INVALID_SESSION_CODES = frozenset({-3009, -3000})

type ChangeCallback = Callable[[LoginCredentials], Awaitable[None]]


class Account:
    """A logged-in account of the bot in one game.

    It logs in when it has no session, logs in again when the server rejects the
    session, and keeps the new key the server offers; every change to the
    credentials goes to ``on_change`` to be stored.
    """

    def __init__(
        self,
        game: Game,
        server: Server,
        credentials: LoginCredentials,
        *,
        on_change: ChangeCallback | None = None,
    ) -> None:
        self.game = game
        self._server = server
        self._credentials = credentials
        self._on_change = on_change
        self._lock = asyncio.Lock()  # one login / key rotation at a time

    @property
    def credentials(self) -> LoginCredentials:
        return self._credentials

    async def call(
        self, manifest: Manifest, class_: str, method: str, *params: Any
    ) -> dict[str, Any]:
        """Call ``class_.method`` as this account, logging in first if needed."""
        async with self._lock:
            for _ in range(2):
                session = await self._session(manifest)
                answer = await self._server.session_call(
                    manifest, session, class_, method, *params
                )
                if answer.get("code") in INVALID_SESSION_CODES:
                    logger.info("%s: The session was rejected.", self.game.key)
                    await self._apply({"oid": None, "key": None})
                    continue
                await self._take_new_key(manifest, session, answer)
                return answer
        raise ServerError(
            f"{self.game.key}: the session was rejected right after logging in."
        )

    async def _session(self, manifest: Manifest) -> Session:
        if session := self._credentials.session:
            return session
        try:
            result = await self._server.login(self.game, manifest, self._credentials)
        except LoginError as exc:
            await self._apply(exc.updates)
            raise
        await self._apply(result.updates)
        return result.session

    def _offered_key(self, answer: Mapping[str, Any]) -> str | None:
        invoke = answer.get("invoke")
        if not invoke:
            return None
        try:
            key = invoke[0]["params"][0]
        except KeyError, IndexError, TypeError:
            key = None
        if not isinstance(key, str) or not key:
            logger.warning("%s: Unrecognised invoke in an answer.", self.game.key)
            return None
        return key

    async def _take_new_key(
        self, manifest: Manifest, session: Session, answer: Mapping[str, Any]
    ) -> None:
        new_key = self._offered_key(answer)
        if new_key is None or new_key == session.key:
            return
        try:
            await self._server.apply_access_token(manifest, session)
        except ServerError:
            logger.warning(
                "%s: could not apply the new key.", self.game.key, exc_info=True
            )
            return
        await self._apply({"key": new_key})

    async def _apply(self, updates: Mapping[str, Any]) -> None:
        if not updates:
            return
        self._credentials = self._credentials.updated(updates)
        if self._on_change is not None:
            await self._on_change(self._credentials)


class CredentialStore(Protocol):
    """Where credentials are kept (the database)."""

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


def todays_song(answer: Mapping[str, Any]) -> int | None:
    """The song code for the current day, from a ``getWeekPlayMusic`` answer."""
    result = answer.get("result")
    if not isinstance(result, dict):
        return None
    day = result.get("curday")
    for entry in result.get("musicList") or []:
        if isinstance(entry, dict) and entry.get("day") == day:
            try:
                return int(entry["music"])
            except KeyError, TypeError, ValueError:
                return None
    return None


async def fetch_todays_song(account: Account, manifest: Manifest) -> int:
    """The song code of the day from the game's server; ``ServerError`` if the answer has
    none.
    """
    answer = await account.call(manifest, "StarLeague", "getWeekPlayMusic")
    song = todays_song(answer)
    if song is None:
        raise ServerError(f"{account.game.key}: no song of the day in the answer.")
    return song
