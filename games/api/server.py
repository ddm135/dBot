"""The game's HTTP server: encrypted JSON calls, and logging in.

Every call is a JSON object ``{class, method, params}`` sent encrypted with a
fresh IV; the answer comes back encrypted or plain. Sessions are made by
:meth:`Server.login`.
"""

import asyncio
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from games.api.auth import (
    LoginCredentials,
    LoginMethod,
    Session,
    cached_id_token,
    dalcom_access_token,
    fetch_google_id_token,
)
from games.api.crypto import Cipher, CryptoError, random_iv
from games.api.http import DEFAULT_RETRY, RetryPolicy, is_retryable_status, send
from games.api.manifest import Manifest
from games.errors import LoginError, ServerError
from games.models import Game

logger = logging.getLogger(__name__)

ASSET_IGNORE = "true"
API_VERSION = "8"

NICKNAME_IN_USE_CODE = -5000
NICKNAME_UNAVAILABLE_CODE = -5001

__all__ = ["LoginResult", "Server", "Session"]


@dataclass(frozen=True, slots=True)
class LoginResult:
    """A session, and the credential fields the login changed."""

    session: Session
    updates: Mapping[str, Any]


def _session_from(answer: Mapping[str, Any], what: str) -> Session:
    try:
        return Session(
            oid=int(answer["result"]["user"]["objectID"]),
            key=str(answer["invoke"][0]["params"][0]),
        )
    except KeyError, IndexError, TypeError, ValueError:
        raise LoginError(f"{what} was refused (code {answer.get('code')}).") from None


def _fill(
    template: str, credentials: LoginCredentials, version: str, **extra: Any
) -> str:
    """A login request from the credentials' template."""
    values = {
        **credentials.fields,
        "provider": credentials.provider,
        "version": version,
        **extra,
    }
    try:
        return template.format(**values)
    except KeyError, IndexError, ValueError:
        raise LoginError("The login template cannot be filled in.") from None


def _login_ends_with_flag(credentials: LoginCredentials, version: str) -> bool:
    """Whether the SNS login template's last parameter is a boolean (the usual)."""
    template = credentials.fields.get("account")
    if not isinstance(template, str) or not template:
        return True  # without a template, the usual shape
    try:
        params = json.loads(
            _fill(template, credentials, version, access_token="", id_token="")
        )["params"]
    except LoginError, ValueError, KeyError, TypeError:
        return True
    return bool(params) and isinstance(params[-1], bool)


def _payload(class_: str, method: str, *params: Any, **extra: Any) -> str:
    return json.dumps(
        {"class": class_, "method": method, "params": list(params), **extra},
        separators=(",", ":"),
        ensure_ascii=False,
    )


class Server:
    """Calls to a game's server, and the logins that open sessions for them."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        cipher: Cipher,
        *,
        retry: RetryPolicy = DEFAULT_RETRY,
    ) -> None:
        self._client = client
        self._cipher = cipher
        self._retry = retry

    async def call(self, server_url: str, payload: str) -> dict[str, Any]:
        """Send an encrypted request to ``server_url`` and return the decoded answer."""
        iv = random_iv()
        try:
            response = await send(
                self._client,
                "POST",
                server_url,
                headers={
                    "X-SuperStar-AES-IV": iv,
                    "X-SuperStar-Asset-Ignore": ASSET_IGNORE,
                    "X-SuperStar-API-Version": API_VERSION,
                },
                content=self._cipher.encrypt_cbc(payload, iv).encode(),
                retry=self._retry,
            )
        except httpx.TransportError as exc:
            raise ServerError(
                f"Could not reach the game server: {exc!r}", retryable=True
            ) from exc

        if is_retryable_status(response.status_code):
            raise ServerError(
                f"The game server answered {response.status_code}.", retryable=True
            )
        return self._decode(response, iv)

    def _decode(self, response: httpx.Response, iv: str) -> dict[str, Any]:
        text = response.text
        try:
            try:
                result = json.loads(text)
            except json.JSONDecodeError:
                result = json.loads(self._cipher.decrypt_cbc(text, iv))
        except CryptoError, ValueError:
            raise ServerError(
                f"The game server's answer was unreadable (HTTP {response.status_code})."
            ) from None
        if not isinstance(result, dict):
            raise ServerError("The game server's answer is not a JSON object.")
        return result

    async def check_asset_bundle(self, manifest: Manifest) -> dict[str, Any]:
        return await self.call(
            manifest.server_url, _payload("Platform", "checkAssetBundle", 0)
        )

    async def check_sns(
        self,
        manifest: Manifest,
        credentials: LoginCredentials,
        token: str,
        version: str,
    ) -> bool:
        """Whether the account exists. Like the login, it takes a trailing ``False``
        only on the games whose login template ends with one."""
        params: list[Any] = [credentials.provider, token]
        if _login_ends_with_flag(credentials, version):
            params.append(False)
        answer = await self.call(
            manifest.server_url, _payload("Account", "checkSNS", *params)
        )
        try:
            return bool(answer["result"]["isSigned"])
        except KeyError, TypeError:
            raise LoginError(f"checkSNS failed (code {answer.get('code')}).") from None

    async def login_sns(
        self,
        manifest: Manifest,
        credentials: LoginCredentials,
        token: str,
        version: str,
    ) -> Session:
        """Log in with a token. The credentials' ``account`` template, when there
        is one, gives the exact request the game expects (the games differ in
        their trailing parameters); without it the usual shape is sent."""
        template = credentials.fields.get("account")
        if isinstance(template, str) and template:
            request = _fill(
                template,
                credentials,
                version,
                access_token=token,
                id_token=token,
            )
        else:
            request = _payload(
                "Account",
                "loginSNS",
                credentials.provider,
                token,
                1,
                version,
                False,
                ptDelta=1,
            )
        return _session_from(await self.call(manifest.server_url, request), "loginSNS")

    async def session_call(
        self,
        manifest: Manifest,
        session: Session,
        class_: str,
        method: str,
        *params: Any,
    ) -> dict[str, Any]:
        """A call made as a logged-in session."""
        return await self.call(
            manifest.server_url,
            _payload(class_, method, session.oid, session.key, *params),
        )

    async def apply_access_token(self, manifest: Manifest, session: Session) -> None:
        await self.session_call(manifest, session, "Account", "applyAccessToken")

    async def create_authentication(self, manifest: Manifest) -> tuple[str, str]:
        """Ask the server for a new user id and local password, for registering an account."""
        answer = await self.call(
            manifest.server_url, _payload("Account", "createAuthentication")
        )
        try:
            result = answer["result"]
            return str(result["userID"]), str(result["localPassword"])
        except KeyError, TypeError:
            raise LoginError(
                f"createAuthentication failed (code {answer.get('code')})."
            ) from None

    async def create_sns_account(
        self,
        manifest: Manifest,
        user_id: str,
        local_password: str,
        provider: int,
        token: str,
        nickname: str,
    ) -> None:
        """Register a new account behind a provider's token under ``nickname``."""
        answer = await self.call(
            manifest.server_url,
            _payload(
                "Account",
                "createSNSAccount",
                0,
                user_id,
                local_password,
                provider,
                token,
                nickname,
                1,
                1,
            ),
        )
        code = answer.get("code")
        if code == 1000:
            return
        if code == NICKNAME_IN_USE_CODE:
            raise LoginError(f"The nickname {nickname!r} is already in use.")
        if code == NICKNAME_UNAVAILABLE_CODE:
            raise LoginError(f"The nickname {nickname!r} is not available.")
        raise LoginError(f"createSNSAccount failed (code {code}).")

    async def register_sns_account(
        self, manifest: Manifest, provider: int, token: str, nickname: str
    ) -> None:
        user_id, local_password = await self.create_authentication(manifest)
        await self.create_sns_account(
            manifest, user_id, local_password, provider, token, nickname
        )

    async def login(
        self,
        game: Game,
        manifest: Manifest,
        credentials: LoginCredentials,
    ) -> LoginResult:
        """Log in to a game with its stored credentials.

        Registers the account first if the provider has none. Raises ``LoginError``;
        whatever was refreshed on the way is in its ``updates``.
        """
        method = credentials.method_for(game)
        if method is None:
            raise LoginError(
                f"{game.key}: provider {credentials.provider} is not supported."
            )

        updates: dict[str, Any] = {}
        try:
            version = manifest.latest_version(game.version_floor)
            if method is LoginMethod.CLASSIC:
                session = await self._login_classic(manifest, credentials, version)
            else:
                token = await self._sns_token(game, method, credentials, updates)
                if not await self.check_sns(manifest, credentials, token, version):
                    logger.warning(
                        "%s: Registering a new account as %r.",
                        game.key,
                        credentials.nickname,
                    )
                    await self.register_sns_account(
                        manifest, credentials.provider, token, credentials.nickname
                    )
                session = await self.login_sns(manifest, credentials, token, version)
        except ServerError as exc:
            if isinstance(exc, LoginError):
                exc.updates = {**updates, **exc.updates}
                raise
            raise LoginError(
                str(exc), retryable=exc.retryable, updates=updates
            ) from exc

        updates.update(oid=session.oid, key=session.key)
        return LoginResult(session, updates)

    async def _login_classic(
        self, manifest: Manifest, credentials: LoginCredentials, version: str
    ) -> Session:
        template = credentials.fields.get("account")
        if not isinstance(template, str) or not template:
            raise LoginError("The credentials have no account template.")
        request = _fill(template, credentials, version)
        return _session_from(await self.call(manifest.server_url, request), "The login")

    async def _sns_token(
        self,
        game: Game,
        method: LoginMethod,
        credentials: LoginCredentials,
        updates: dict[str, Any],
    ) -> str:
        if method is LoginMethod.GOOGLE:
            return await self._google_token(game, credentials, updates)
        assert game.dalcom_authorization
        token, fresh = await dalcom_access_token(
            self._client,
            game.dalcom_authorization,
            credentials.fields,
            retry=self._retry,
        )
        updates.update(fresh)
        return token

    async def _google_token(
        self, game: Game, credentials: LoginCredentials, updates: dict[str, Any]
    ) -> str:
        assert game.google_audience
        if token := cached_id_token(credentials.fields):
            return token
        service_account = credentials.fields.get("service_account")
        if not service_account:
            raise LoginError("The credentials have no service_account.")
        try:
            token = await asyncio.to_thread(
                fetch_google_id_token, service_account, game.google_audience
            )
        except LoginError:
            raise
        except Exception as exc:
            raise LoginError(f"Google sign-in failed: {exc!r}", retryable=True) from exc
        updates["id_token"] = token
        return token
