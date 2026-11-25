import logging
import os
import socket
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

TRUTHY_VALUES = {"1", "true", "yes", "on"}
DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True, slots=True)
class PostgresSettings:
    host: str
    port: int
    username: str
    password: str | None
    use_tls: bool
    ca_file: Path | None = None  # the server's CA, if it is not a public one
    database: str | None = None  # defaults to the username
    pool_max: int = 2  # each open connection costs the server memory

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Self:
        env = os.environ if env is None else env
        return cls(
            host=env.get("POSTGRES_HOST", "localhost"),
            port=int(env.get("POSTGRES_PORT", "5432")),
            username=env.get("POSTGRES_USERNAME", "dBot"),
            password=env.get("POSTGRES_PASSWORD"),
            use_tls=env.get("POSTGRES_INSECURE", "").lower() not in TRUTHY_VALUES,
            ca_file=Path(ca) if (ca := env.get("POSTGRES_CA_FILE")) else None,
            database=env.get("POSTGRES_DATABASE") or None,
            pool_max=max(1, int(env.get("POSTGRES_POOL_MAX", "2"))),
        )


@dataclass(frozen=True, slots=True)
class ValkeySettings:
    host: str
    port: int
    username: str
    password: str | None
    use_tls: bool

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Self:
        env = os.environ if env is None else env
        return cls(
            host=env.get("VALKEY_HOST") or env.get("REDIS_HOST") or "localhost",
            port=int(env.get("VALKEY_PORT") or env.get("REDIS_PORT") or 6379),
            username=env.get("VALKEY_USERNAME") or env.get("REDIS_USERNAME") or "dBot",
            password=env.get("VALKEY_PASSWORD") or env.get("REDIS_PASSWORD"),
            use_tls=env.get("VALKEY_INSECURE", "").lower() not in TRUTHY_VALUES,
        )


@dataclass(frozen=True, slots=True)
class GoogleSettings:
    """The Google Drive folder that kept borders are uploaded to."""

    credentials_file: Path = Path("dBot.json")  # a service account
    border_folder_id: str = "1FgZltBhxE0G2R93VnEhtNqSC_HtOmA-g"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Self:
        env = os.environ if env is None else env
        default = cls()
        return cls(
            credentials_file=Path(
                env.get("GOOGLE_CREDENTIALS_FILE") or default.credentials_file
            ),
            border_folder_id=env.get("BORDER_FOLDER_ID") or default.border_folder_id,
        )


@dataclass(frozen=True, slots=True)
class Settings:
    discord_token: str
    postgres: PostgresSettings
    valkey: ValkeySettings
    instance_id: str
    aes_key: bytes = field(repr=False)
    google: GoogleSettings = field(default_factory=GoogleSettings)
    log_level: int = logging.INFO

    data_dir: Path = DEFAULT_DATA_DIR

    lease_key: str = "dBot:leader"
    lease_ttl: float = 60.0  # lease lifetime without a renewal
    lease_renew_interval: float = 15.0  # leader renews this often
    lease_poll_interval: float = 5.0  # standby tries this often
    lease_margin: float = 15.0  # leader steps down this long before the TTL ends
    lease_request_timeout: float = 5.0
    restart_cooldown: float = 60.0  # pause after a crash so the standby can win
    close_timeout: float = 15.0  # how long to wait for the bot to close before killing

    # Failback: the preferred instance (the main one) takes leadership back.
    preferred: bool = False
    preferred_healthy_for: float = (
        60.0  # healthy this long before it asks for the lease
    )
    preferred_ttl: float = 15.0  # lifetime of its return signal

    def __post_init__(self) -> None:
        if len(self.aes_key) not in (16, 24, 32):
            raise RuntimeError("AES_KEY must be 16, 24 or 32 bytes long.")

        if self.lease_request_timeout >= self.lease_margin:
            raise RuntimeError(
                "Lease request timeout must be shorter than lease step-down margin."
            )

        if (
            not self.lease_poll_interval + self.lease_request_timeout
            < self.preferred_ttl
            <= self.lease_ttl
        ):
            raise RuntimeError(
                "Preferred TTL must be longer than "
                "lease poll interval and lease request timeout combined "
                "but no longer than lease TTL."
            )

        if (
            self.lease_renew_interval + self.lease_margin + self.lease_request_timeout
            >= self.lease_ttl
        ):
            raise RuntimeError(
                "Lease TTL must be longer than lease renew interval, "
                "lease step-down margin, and lease request timeout combined."
            )

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Self:
        env = os.environ if env is None else env

        token = env.get("DISCORD_TOKEN")
        if not token:
            raise RuntimeError("Missing Discord token.")

        aes_key = env.get("AES_KEY")
        if not aes_key:
            raise RuntimeError("Missing AES key.")

        preferred = env.get("PREFERRED", "").lower() in TRUTHY_VALUES

        return cls(
            discord_token=token,
            postgres=PostgresSettings.from_env(env),
            valkey=ValkeySettings.from_env(env),
            instance_id=socket.gethostname(),
            aes_key=aes_key.encode(),
            google=GoogleSettings.from_env(env),
            preferred=preferred,
        )
