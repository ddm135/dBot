"""A console to inspect the running bot: type ``guilds[0].name``-style paths.

``?`` lists the names on the bot and ``games?`` those under a path.

Input is read by a daemon thread that hands lines to the event loop, so a read
that never returns (nobody types, or the console is closed) cannot hold up
shutdown or Ctrl+C, and nothing a path does can end the listener.
"""

import asyncio
import contextlib
import difflib
import logging
import re
import sys
import threading
from pprint import pformat
from typing import Any

logger = logging.getLogger(__name__)

MAX_OUTPUT = 20_000  # characters; a whole bot printed would flood the console

# Group 1: a dotted attribute. Group 2: a quoted key. Group 3: a list index.
_TOKEN = re.compile(
    r'(?:^|\.)([a-zA-Z_][a-zA-Z0-9_]*)|\[[\'"](.*?)[\'"]\]|\[([0-9]+)\]'
)


def names(obj: object) -> list[str]:
    """The public names under ``obj``, for suggestions and for ``?``."""
    try:
        return sorted(n for n in dir(obj) if not n.startswith("_"))
    except Exception:  # noqa: BLE001 - a broken __dir__
        return []


def _hint(obj: object, attr: str) -> str:
    close = difflib.get_close_matches(attr, names(obj), n=3, cutoff=0.5)
    return f" Did you mean: {', '.join(close)}?" if close else " Type ? to list names."


class LookupFailed(Exception):
    """A path that cannot be followed; the message says where it stopped."""


def lookup(root: object, path: str) -> object:
    """Follow ``attr``, ``['key']`` and ``[0]`` steps from ``root``."""
    if path == "bot":
        return root
    path = path.removeprefix("bot.")
    tokens = _TOKEN.findall(path)
    if not tokens:
        raise LookupFailed(f"Could not parse '{path}'.")
    current: Any = root
    for attr, key, idx in tokens:
        try:
            if attr:
                current = getattr(current, attr)
            elif key:
                if not isinstance(current, dict) or key not in current:
                    raise LookupFailed(
                        f"Key '{key}' not found or object is not a dict along path '{path}'."
                    )
                current = current[key]
            else:
                number = int(idx)
                if not isinstance(current, list | tuple) or number >= len(current):
                    raise LookupFailed(
                        f"Index [{number}] out of range or not a sequence along path '{path}'."
                    )
                current = current[number]
        except LookupFailed:
            raise
        except AttributeError:
            raise LookupFailed(
                f"Attribute '{attr}' does not exist along path '{path}'."
                + _hint(current, attr)
            ) from None
        except Exception as error:  # noqa: BLE001 - a property that raises
            raise LookupFailed(
                f"'{attr or key or idx}' failed along path '{path}': {error!r}"
            ) from None
    return current


def render(value: object) -> str:
    try:
        text = pformat(value)
    except Exception as error:  # noqa: BLE001 - a repr that raises
        return f"Could not print the value: {error!r}"
    if len(text) > MAX_OUTPUT:
        return text[:MAX_OUTPUT] + f"\n... ({len(text) - MAX_OUTPUT} more characters)"
    return text


def _read_lines(
    loop: asyncio.AbstractEventLoop, lines: asyncio.Queue[str | None]
) -> None:
    """Runs in a daemon thread; ``None`` marks the end of the input."""
    try:
        for line in sys.stdin:  # ends at EOF (Ctrl+Z, Ctrl+D) or a closed console
            loop.call_soon_threadsafe(lines.put_nowait, line)
    except BaseException:  # a Ctrl+C or a broken console ends the reader
        logger.debug("Console input failed.", exc_info=True)
    with contextlib.suppress(RuntimeError):  # the loop may already be closed
        loop.call_soon_threadsafe(lines.put_nowait, None)


async def listen(bot: object) -> None:
    if not sys.stdin or not sys.stdin.isatty():
        logger.info("No interactive TTY found. Console listener disabled.")
        return

    logger.info("Console listener enabled.")
    lines: asyncio.Queue[str | None] = asyncio.Queue()
    threading.Thread(
        target=_read_lines,
        args=(asyncio.get_running_loop(), lines),
        name="console",
        daemon=True,
    ).start()

    while (line := await lines.get()) is not None:
        path = line.strip()
        if not path:
            continue
        try:
            if path.endswith("?"):  # "?" lists the bot's names, "games?" a path's
                output = ", ".join(names(lookup(bot, path[:-1].rstrip(".")))) or "-"
            else:
                output = render(lookup(bot, path))
        except LookupFailed as error:
            output = f"Error: {error}"
        except Exception:
            logger.exception("Console command failed: %s", path)
            continue
        try:
            print(output, flush=True)
        except Exception:  # a closed or broken console
            logger.debug("Could not write to the console.", exc_info=True)
            return
    logger.info("Console input closed. Console listener stopped.")
