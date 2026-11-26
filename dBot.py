"""The entry point: ``python dBot.py``. Reads the settings, imports every
extension up front, and hands over to :func:`app.run`.
"""

import asyncio
import importlib

from discord.utils import setup_logging
from dotenv import load_dotenv

from app import run
from config import Settings
from extensions import EXTENSIONS
from tuning import limit_arenas


def main() -> None:
    """Configure the process and run the bot until it is told to stop."""
    limit_arenas()  # before any thread exists
    load_dotenv()
    try:
        settings = Settings.from_env()
    except RuntimeError as exc:
        raise SystemExit(f"Configuration error:\n{exc}") from None

    setup_logging(level=settings.log_level)
    # Importing the extensions (and the big libraries behind them) takes seconds
    # on a slow disk. Done here, nothing is waiting on the event loop yet; done
    # while loading them, the lease cannot be renewed meanwhile.
    for name in EXTENSIONS:
        importlib.import_module(name)
    asyncio.run(run(settings))


if __name__ == "__main__":
    main()
