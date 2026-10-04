from typing import Any

from .base import SCRIPTS, BaseLease


class ValkeyLease(BaseLease):
    async def connect(self, request_timeout: float) -> None:
        from valkey.asyncio import Valkey

        self._client: Valkey | None = Valkey(
            host=self._settings.host,
            port=self._settings.port,
            ssl=self._settings.use_tls,
            username=self._settings.username,
            password=self._settings.password,
            socket_timeout=request_timeout,
            socket_connect_timeout=request_timeout,
        )
        await self._client.ping()
        self._scripts = {
            name: self._client.register_script(script)
            for name, script in SCRIPTS.items()
        }

    async def _run(
        self,
        script: str,
        keys: list[str | bytes | bytearray | memoryview] | None = None,
        args: list[str | bytes | bytearray | memoryview] | None = None,
    ) -> Any:
        for items in (keys, args):
            if items is None:
                continue

            for i, item in enumerate(items):
                if isinstance(item, bytearray):
                    items[i] = memoryview(item)

        return await self._scripts[script](keys=keys, args=args)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
