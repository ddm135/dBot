from typing import Any

from config import ValkeySettings

ACQUIRE_OR_RENEW = """
local holder = redis.call('GET', KEYS[1])
if holder == ARGV[1] then
    redis.call('PEXPIRE', KEYS[1], ARGV[2])
    return 1
end
if not holder then
    redis.call('SET', KEYS[1], ARGV[1], 'PX', ARGV[2])
    return 1
end
return 0
"""

RELEASE = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""

EXISTS = """
return redis.call('EXISTS', KEYS[1])
"""

SCRIPTS = {
    "acquire": ACQUIRE_OR_RENEW,
    "release": RELEASE,
    "exists": EXISTS,
}


class BaseLease:
    def __init__(
        self,
        settings: ValkeySettings,
        /,
        key: str,
        holder: str,
        ttl: float,
        *,
        preferred_key: str | None = None,
        preferred_ttl: float = 15.0,
    ) -> None:
        self._settings = settings
        self._key = key
        self._holder = holder
        self._ttl_ms = str(int(ttl * 1000))
        self._preferred_key = preferred_key or f"{key}:preferred"
        self._preferred_ttl_ms = str(int(preferred_ttl * 1000))
        self._client: Any = None
        self._scripts: dict[str, Any] = {}

    async def connect(self, request_timeout: float) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError

    async def _run(
        self,
        script: str,
        keys: list[str | bytes | bytearray | memoryview] | None = None,
        args: list[str | bytes | bytearray | memoryview] | None = None,
    ) -> Any:
        raise NotImplementedError

    async def acquire_or_renew(self) -> bool:
        """True if the caller holds the lease after this call."""

        result = await self._run("acquire", [self._key], [self._holder, self._ttl_ms])
        return result == 1

    async def release(self) -> None:
        """Give the lease up, but only if the caller holds it."""

        await self._run("release", [self._key], [self._holder])

    async def advertise_preferred(self) -> None:
        """Advertise that the preferred instance is up for a short time."""

        await self._run(
            "acquire",
            [self._preferred_key],
            [self._holder, self._preferred_ttl_ms],
        )

    async def preferred_waiting(self) -> bool:
        """True while a preferred instance is advertising."""

        result = await self._run("exists", [self._preferred_key])
        return result == 1
