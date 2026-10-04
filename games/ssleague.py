"""The Star League song of the day."""

from collections.abc import Mapping
from typing import Any

from .account import Account
from .errors import ServerError
from .manifest import Manifest


def todays_song(answer: Mapping[str, Any]) -> int | None:
    """The song code for the current day, from a ``getWeekPlayMusic`` answer."""
    result = answer.get("result")
    if not isinstance(result, dict):
        return None
    day = result.get("curday")
    for entry in result.get("musicList") or []:
        if isinstance(entry, dict) and entry.get("day") == day:
            try:
                return int(entry["music"])
            except KeyError, TypeError, ValueError:
                return None
    return None


async def fetch_todays_song(account: Account, manifest: Manifest) -> int:
    answer = await account.call(manifest, "StarLeague", "getWeekPlayMusic")
    song = todays_song(answer)
    if song is None:
        raise ServerError(f"{account.game.key}: no song of the day in the answer.")
    return song
