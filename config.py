import logging
import os
import socket
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Self
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class PostgresSettings:
    host: str
    port: int
    username: str
    password: str | None
    use_tls: bool = False

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Self:
        env = os.environ if env is None else env
        return cls(
            host=env.get("POSTGRES_HOST", "localhost"),
            port=int(env.get("POSTGRES_PORT", "5432")),
            username=env.get("POSTGRES_USERNAME", "dBot"),
            password=env.get("POSTGRES_PASSWORD"),
        )


@dataclass(frozen=True, slots=True)
class ValkeySettings:
    host: str
    port: int
    username: str
    password: str | None
    use_tls: bool


@dataclass(frozen=True, slots=True)
class Settings:
    discord_token: str
    postgres: PostgresSettings
    valkey: ValkeySettings
    instance_id: str

    lease_key: str = "dBot:leader"
    lease_ttl: float = 30.0  # lease lifetime without a renewal
    lease_renew_every: float = 10.0  # leader renews this often
    lease_poll_every: float = 5.0  # standby tries this often
    lease_margin: float = 5.0  # leader steps down this long *before* the TTL ends
    lease_request_timeout: float = 3.0
    restart_cooldown: float = 60.0  # pause after a crash so the standby can win
    log_level: int = logging.INFO

    # Failback: the preferred instance (the main one) takes leadership back.
    preferred: bool = False
    preferred_healthy_for: float = (
        60.0  # healthy this long before it asks for the lease
    )
    preferred_ttl: float = 15.0  # lifetime of its return signal

    def __post_init__(self) -> None:
        if self.lease_request_timeout >= self.lease_margin:
            raise RuntimeError

        if (
            not self.lease_poll_every + self.lease_request_timeout
            < self.preferred_ttl
            <= self.lease_ttl
        ):
            raise RuntimeError

        if (
            self.lease_renew_every + self.lease_margin + self.lease_request_timeout
            >= self.lease_ttl
        ):
            raise RuntimeError

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Self:
        env = os.environ if env is None else env

        token = env.get("DISCORD_TOKEN")
        if not token:
            raise RuntimeError("Missing Discord token.")

        valkey_host = (
            env.get("VALKEY_HOST") or env.get("REDIS_HOST") or "redis://localhost"
        )
        valkey_port = int(env.get("VALKEY_PORT") or env.get("REDIS_HOST") or 6379)
        valkey_username = (
            env.get("VALKEY_USERNAME") or env.get("REDIS_USERNAME") or "dBot"
        )
        valkey_password = env.get("VALKEY_PASSWORD") or env.get("REDIS_PASSWORD")
        parsed_valkey_host = urlsplit(valkey_host)

        preferred = env.get("PREFERRED", False) in {"1", "true", "yes", "on"}

        return cls(
            discord_token=token,
            postgres=PostgresSettings.from_env(env),
            valkey=ValkeySettings(
                host=parsed_valkey_host.hostname or "localhost",
                port=valkey_port,
                username=valkey_username,
                password=valkey_password,
                use_tls=parsed_valkey_host.scheme in {"valkeys", "rediss"},
            ),
            instance_id=socket.gethostname(),
            preferred=preferred,
        )
