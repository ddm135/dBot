from typing import Any

from .base import SCRIPTS, BaseLease


class GlideLease(BaseLease):
    async def connect(self, request_timeout: float) -> None:
        from glide import (
            GlideClient,
            GlideClientConfiguration,
            NodeAddress,
            Script,
            ServerCredentials,
        )

        credentials = ServerCredentials(
            username=self._settings.username, password=self._settings.password
        )
        config = GlideClientConfiguration(
            [NodeAddress(self._settings.host, self._settings.port)],
            use_tls=self._settings.use_tls,
            credentials=credentials,
            request_timeout=int(request_timeout * 1000),
        )

        self._client: GlideClient | None = await GlideClient.create(config)
        self._scripts = {name: Script(script) for name, script in SCRIPTS.items()}

    async def _run(
        self,
        script: str,
        keys: list[str | bytes | bytearray | memoryview] | None = None,
        args: list[str | bytes | bytearray | memoryview] | None = None,
    ) -> Any:
        assert self._client
        return await self._client.invoke_script(
            self._scripts[script], keys=keys, args=args
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
