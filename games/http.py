import asyncio
import logging
import os
import random
from collections.abc import Callable, Container
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    before_sleep_log,
    retry_if_exception,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
)

from .errors import ServerError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
CHUNK_SIZE = 256 * 1024
FLUSH_EVERY = 32 * 1024 * 1024  # bytes written between handing pages back to the OS


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    attempts: int = 3
    initial: float = 1.0
    maximum: float = 15.0
    jitter: float = 1.0


DEFAULT_RETRY = RetryPolicy()


def create_client(**kwargs: Any) -> httpx.AsyncClient:
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    kwargs.setdefault("follow_redirects", True)
    kwargs.setdefault(
        "limits", httpx.Limits(max_connections=20, max_keepalive_connections=10)
    )
    return httpx.AsyncClient(**kwargs)


def is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    return isinstance(exc, httpx.HTTPStatusError) and is_retryable_status(
        exc.response.status_code
    )


def _wait(policy: RetryPolicy) -> Callable[[RetryCallState], float]:
    def wait(state: RetryCallState) -> float:
        delay = policy.initial * 2.0 ** (state.attempt_number - 1)
        return min(delay + random.uniform(0, policy.jitter), policy.maximum)

    return wait


def _retrying(policy: RetryPolicy, **kwargs: Any) -> AsyncRetrying:
    return AsyncRetrying(
        stop=stop_after_attempt(policy.attempts),
        wait=_wait(policy),
        before_sleep=before_sleep_log(logger, logging.INFO),
        **kwargs,
    )


def _last_outcome(state: RetryCallState) -> Any:
    assert state.outcome is not None
    return state.outcome.result()


async def send(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    retry: RetryPolicy = DEFAULT_RETRY,
    **kwargs: Any,
) -> httpx.Response:
    retrying = _retrying(
        retry,
        retry=(
            retry_if_exception_type(httpx.TransportError)
            | retry_if_result(lambda r: is_retryable_status(r.status_code))
        ),
        retry_error_callback=_last_outcome,
    )
    response: httpx.Response = await retrying(client.request, method, url, **kwargs)
    return response


async def fetch(
    client: httpx.AsyncClient,
    url: str,
    *,
    retry: RetryPolicy = DEFAULT_RETRY,
    error: type[ServerError] = ServerError,
    ok: Container[int] = (200,),
) -> httpx.Response:
    """GET a URL, raising ``error`` unless the answer's status is in ``ok``.

    Network trouble and server-side statuses are marked retryable.
    """
    try:
        response = await send(client, "GET", url, retry=retry)
    except httpx.TransportError as exc:
        raise error(f"Could not reach {url}: {exc!r}", retryable=True) from exc
    if response.status_code not in ok:
        raise error(
            f"{url} answered {response.status_code}.",
            retryable=is_retryable_status(response.status_code),
        )
    return response


def release_pages(file: Any) -> None:
    """Write what a file holds to disk and drop it from the page cache.

    A container's memory meter counts the cache, so downloading many bundles
    would show as ever more RAM in use even though nothing is held. The files are
    read back from disk when needed, so keeping their pages cached gains little.
    """
    try:
        file.flush()
        os.fsync(file.fileno())
        if hasattr(os, "posix_fadvise"):  # Linux, not Windows
            os.posix_fadvise(file.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
    except OSError:
        logger.debug("Could not release a file's pages.", exc_info=True)


async def download(
    client: httpx.AsyncClient,
    url: str,
    path: Path,
    *,
    retry: RetryPolicy = DEFAULT_RETRY,
    chunk_size: int = CHUNK_SIZE,
) -> Path:
    partial = path.with_name(path.name + ".part")
    await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)

    async def attempt() -> None:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            file = await asyncio.to_thread(open, partial, "wb")
            try:
                since = 0
                async for chunk in response.aiter_bytes(chunk_size):
                    await asyncio.to_thread(file.write, chunk)
                    since += len(chunk)
                    if since >= FLUSH_EVERY:
                        since = 0
                        await asyncio.to_thread(release_pages, file)
                await asyncio.to_thread(release_pages, file)
            finally:
                await asyncio.to_thread(file.close)

    try:
        await _retrying(retry, retry=retry_if_exception(_is_transient), reraise=True)(
            attempt
        )
        await asyncio.to_thread(os.replace, partial, path)
    except BaseException:
        await asyncio.to_thread(partial.unlink, missing_ok=True)
        raise
    return path
