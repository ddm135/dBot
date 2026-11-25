import asyncio

from discord.utils import setup_logging
from dotenv import load_dotenv

from app import run
from config import Settings
from tuning import limit_arenas


def main() -> None:
    limit_arenas()  # before any thread exists
    load_dotenv()
    try:
        settings = Settings.from_env()
    except RuntimeError as exc:
        raise SystemExit(f"Configuration error:\n{exc}") from None

    setup_logging(level=settings.log_level)
    asyncio.run(run(settings))


if __name__ == "__main__":
    main()
