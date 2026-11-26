"""Logging in to a game: which method a stored account uses, and the tokens for it.

The games sign in with a Google ID token (from a service account), a Dalcom ID
access token, or a plain game account. The credentials of an account are a
mapping kept in the database; refreshed tokens are returned as ``updates`` for
the caller to store.
"""

import enum
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Self

import httpx
from google.auth import jwt
from google.auth.exceptions import TransportError
from google.auth.transport import Request, Response
from google.oauth2.service_account import IDTokenCredentials

from games.api.http import DEFAULT_RETRY, RetryPolicy, is_retryable_status, send
from games.errors import LoginError
from games.models import Game

DALCOM_API_URL = "https://oauth.dalcomsoft.net/v1"
DALCOM_EXPIRED_TOKEN_CODES = frozenset({-114, -116, -300})  # expired/invalid/empty
DALCOM_INVALID_REFRESH_TOKEN_CODE = -112
DALCOM_MAX_ROUNDS = 3

# An ID token that expires within this many seconds is not worth reusing.
GOOGLE_TOKEN_MARGIN = 60.0

# The nickname new accounts are registered under. Nicknames are unique per
# game, so a different one can be stored per account as ``nickname``.
DEFAULT_NICKNAME = "dBot"


class LoginMethod(enum.Enum):
    """How an account signs in."""

    CLASSIC = enum.auto()
    GOOGLE = enum.auto()
    DALCOM = enum.auto()


@dataclass(frozen=True, slots=True)
class Session:
    """A logged-in session: the user's object id and the key that signs its calls."""

    oid: int
    key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class LoginCredentials:
    """What the database stores for an account: the provider and its fields (ids,
    tokens, the login request template, the session once there is one).
    """

    provider: int
    fields: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> Self:
        """The credentials from a stored mapping; ``LoginError`` if it has no provider."""
        try:
            return cls(provider=int(data["provider"]), fields=dict(data))
        except (KeyError, TypeError, ValueError) as exc:
            raise LoginError(
                f"The stored credentials have no provider: {exc!r}."
            ) from exc

    @property
    def is_sns(self) -> bool:
        """Whether the account signs in through a provider (Google or Dalcom ID) rather
        than a game account.
        """
        return bool(self.fields.get("isSNS", True))

    @property
    def nickname(self) -> str:
        """The nickname to register a new account under."""
        return str(self.fields.get("nickname") or DEFAULT_NICKNAME)

    def method_for(self, game: Game) -> LoginMethod | None:
        """How to log in to ``game`` with these credentials, or None if they do not fit it."""
        match self.provider:
            case 0 | 1 if not self.is_sns:
                return LoginMethod.CLASSIC
            case 0 if game.google_audience:
                return LoginMethod.GOOGLE
            case 3 if self.is_sns and game.dalcom_authorization:
                return LoginMethod.DALCOM
        return None

    @property
    def session(self) -> Session | None:
        """The stored session, if there is one."""
        oid, key = self.fields.get("oid"), self.fields.get("key")
        if not oid or not key:
            return None
        try:
            return Session(int(oid), str(key))
        except TypeError, ValueError:
            return None

    def updated(self, updates: Mapping[str, Any]) -> Self:
        """A copy with ``updates`` applied (a None value empties a field)."""
        return type(self)(self.provider, {**self.fields, **updates})


def jwt_expiry(token: str) -> float | None:
    """When a JWT expires (a Unix time), or None if it cannot be read."""
    try:
        return float(jwt.decode(token, verify=False)["exp"])
    except ValueError, KeyError, TypeError:
        return None


def cached_id_token(
    fields: Mapping[str, Any], *, now: float | None = None
) -> str | None:
    """The stored Google ID token if it is still good for a while, else None."""
    token = fields.get("id_token")
    if not isinstance(token, str) or not token:
        return None
    expiry = jwt_expiry(token)
    if expiry is None:
        return None
    now = time.time() if now is None else now
    return token if expiry - GOOGLE_TOKEN_MARGIN > now else None


class _HttpxResponse(Response):
    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    @property
    def status(self) -> int:
        return self._response.status_code

    @property
    def headers(self) -> Mapping[str, str]:
        return self._response.headers

    @property
    def data(self) -> bytes:
        return self._response.content


class _HttpxRequest(Request):
    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def __call__(
        self,
        url: str,
        method: str = "GET",
        body: bytes | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> Response:
        try:
            response = self._client.request(
                method, url, content=body, headers=headers, timeout=timeout
            )
        except httpx.HTTPError as exc:
            raise TransportError(exc) from exc
        return _HttpxResponse(response)


def fetch_google_id_token(
    service_account: str | Path | Mapping[str, Any],
    audience: str,
    *,
    transport: httpx.BaseTransport | None = None,
) -> str:
    """A Google ID token for ``audience``, from a service account (a key file or its contents).

    Blocking; call it in a thread.
    """
    target = f"{audience}.apps.googleusercontent.com"
    if isinstance(service_account, Mapping):
        credentials = IDTokenCredentials.from_service_account_info(
            dict(service_account), target_audience=target
        )
    elif isinstance(service_account, str | Path):
        credentials = IDTokenCredentials.from_service_account_file(
            str(service_account), target_audience=target
        )
    else:
        raise LoginError("The service account is neither a file path nor a key.")

    with httpx.Client(transport=transport, timeout=30.0) as client:
        credentials.refresh(_HttpxRequest(client))
    token = credentials.token
    if not token:
        raise LoginError("Google did not return an ID token.")
    return str(token)


async def _dalcom_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    retry: RetryPolicy,
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        response = await send(client, method, url, retry=retry, **kwargs)
    except httpx.TransportError as exc:
        raise LoginError(
            f"Could not reach the Dalcom ID server: {exc!r}", retryable=True
        ) from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise LoginError(
            f"Dalcom ID answered with something that is not JSON "
            f"(HTTP {response.status_code}).",
            retryable=is_retryable_status(response.status_code),
        ) from exc
    if not isinstance(data, dict):
        raise LoginError("Dalcom ID answered with something that is not an object.")
    return data


def _json_body(data: Mapping[str, Any]) -> bytes:
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode()


def _token_pair(answer: Mapping[str, Any]) -> tuple[str, str]:
    try:
        data = answer["data"]
        return str(data["access_token"]), str(data["refresh_token"])
    except (KeyError, TypeError) as exc:
        raise LoginError(
            f"Dalcom ID refused the login: {answer.get('message') or answer.get('code')}."
        ) from exc


async def dalcom_access_token(
    client: httpx.AsyncClient,
    authorization: str,
    fields: Mapping[str, Any],
    *,
    retry: RetryPolicy = DEFAULT_RETRY,
) -> tuple[str, dict[str, Any]]:
    """A Dalcom ID access token, and the changes to store with the credentials.

    Uses the stored tokens when they still work, refreshes them when they have
    expired, and falls back to the id and password when the refresh token is
    rejected too. ``LoginError.updates`` carries what changed even on failure.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {authorization}",
    }
    access = str(fields.get("access_token") or "")
    refresh = str(fields.get("refresh_token") or "")
    updates: dict[str, Any] = {}

    try:
        for _ in range(DALCOM_MAX_ROUNDS):
            if not access and not refresh:
                account_id, password = fields.get("id"), fields.get("pass")
                if not account_id or not password:
                    raise LoginError(
                        "The Dalcom ID credentials have no id and/or pass."
                    )
                answer = await _dalcom_json(
                    client,
                    "POST",
                    f"{DALCOM_API_URL}/token",
                    retry,
                    headers=headers,
                    content=_json_body(
                        {"id": account_id, "pass": password, "grant_type": "password"}
                    ),
                )
                if answer.get("code") != 200:  # wrong id or password
                    raise LoginError(
                        f"Dalcom ID refused the login: {answer.get('message')}."
                    )
                access, refresh = _token_pair(answer)
                updates.update(access_token=access, refresh_token=refresh)

            user = await _dalcom_json(
                client,
                "GET",
                f"{DALCOM_API_URL}/user",
                retry,
                headers=headers,
                params={"access_token": access},
            )
            if user.get("code") not in DALCOM_EXPIRED_TOKEN_CODES:
                return access, updates

            answer = await _dalcom_json(
                client,
                "POST",
                f"{DALCOM_API_URL}/token",
                retry,
                headers=headers,
                content=_json_body(
                    {"refresh_token": refresh, "grant_type": "refresh_token"}
                ),
            )
            if answer.get("code") == DALCOM_INVALID_REFRESH_TOKEN_CODE:
                access = refresh = ""
                updates.update(access_token=None, refresh_token=None)
                continue  # start over with id/pass
            access, refresh = _token_pair(answer)
            updates.update(access_token=access, refresh_token=refresh)
            return access, updates
    except LoginError as exc:
        exc.updates = {**updates, **exc.updates}
        raise

    raise LoginError("The Dalcom ID login did not settle.", updates=updates)
