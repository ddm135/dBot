import asyncio

from discord.utils import setup_logging
from dotenv import load_dotenv

from app import run
from config import Settings

# from v0.dBot import main


def main() -> None:
    load_dotenv()
    try:
        settings = Settings.from_env()
    except RuntimeError as exc:
        raise SystemExit(f"Configuration error:\n{exc}") from None

    setup_logging()
    asyncio.run(run(settings))


if __name__ == "__main__":
    main()
