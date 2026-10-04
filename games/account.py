import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from .auth import LoginCredentials, Session
from .errors import LoginError, ServerError
from .manifest import Manifest
from .models import Game
from .server import Server

logger = logging.getLogger(__name__)

INVALID_SESSION_CODES = frozenset({-3009, -3000})

type ChangeCallback = Callable[[LoginCredentials], Awaitable[None]]


class Account:
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
