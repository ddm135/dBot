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
from collections.abc import Mapping
from pprint import pformat
from typing import Any

logger = logging.getLogger(__name__)

MAX_OUTPUT = 20_000  # characters; a whole bot printed would flood the console

# Group 1: a dotted attribute. Group 2: a quoted key. Group 3: a list index.
_TOKEN = re.compile(
    r'(?:^|\.)([a-zA-Z_][a-zA-Z0-9_]*)|\[[\'"](.*?)[\'"]\]|\[([0-9]+)\]'
)


def _keys_hint(mapping: Mapping[Any, Any]) -> str:
    return f" Keys: {', '.join(str(k) for k in list(mapping)[:30])}."


def names(obj: object) -> list[str]:
    """The public names under ``obj``, for suggestions and for ``?``.

    For a mapping (``cogs``, a dict) these are its keys, to use as ``['key']``.
    """
    if isinstance(obj, Mapping):
        return sorted(str(k) for k in obj)
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
                if not isinstance(current, Mapping) or key not in current:
                    raise LookupFailed(
                        f"Key '{key}' not found or object is not a mapping along path '{path}'."
                        + (_keys_hint(current) if isinstance(current, Mapping) else "")
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


class _Reader:
    """One thread reads the console for the life of the process.

    A thread blocked on stdin cannot be stopped, so a new one for every restart
    would pile up (each holding memory, and taking input meant for the current
    listener). Instead the single thread hands lines to whichever listener is
    attached right now.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sink: tuple[asyncio.AbstractEventLoop, asyncio.Queue[str | None]] | None
        self._sink = None
        self._thread: threading.Thread | None = None
        self._ended = False

    def attach(
        self, loop: asyncio.AbstractEventLoop, lines: asyncio.Queue[str | None]
    ) -> None:
        with self._lock:
            self._sink = (loop, lines)
            if self._ended:
                lines.put_nowait(None)
            elif self._thread is None:
                self._thread = threading.Thread(
                    target=self._read, name="console", daemon=True
                )
                self._thread.start()

    def detach(self, lines: asyncio.Queue[str | None]) -> None:
        with self._lock:
            if self._sink is not None and self._sink[1] is lines:
                self._sink = None

    def _send(self, line: str | None) -> None:
        with self._lock:
            sink = self._sink
        if sink is not None:
            with contextlib.suppress(RuntimeError):  # the loop may be closed
                sink[0].call_soon_threadsafe(sink[1].put_nowait, line)

    def _read(self) -> None:
        try:
            for line in sys.stdin:  # ends at EOF (Ctrl+Z, Ctrl+D) or a closed console
                self._send(line)
        except BaseException:  # a Ctrl+C or a broken console ends the reader
            logger.debug("Console input failed.", exc_info=True)
        with self._lock:
            self._ended = True
        self._send(None)


_reader = _Reader()


async def listen(bot: object) -> None:
    if not sys.stdin or not sys.stdin.isatty():
        logger.info("No interactive TTY found. Console listener disabled.")
        return

    logger.info("Console listener enabled.")
    lines: asyncio.Queue[str | None] = asyncio.Queue()
    _reader.attach(asyncio.get_running_loop(), lines)
    try:
        await _serve(bot, lines)
    finally:
        _reader.detach(lines)


async def _serve(bot: object, lines: asyncio.Queue[str | None]) -> None:
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
