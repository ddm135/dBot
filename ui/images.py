"""Turning a :class:`Picture` into something an embed can show."""

from dataclasses import dataclass
from io import BytesIO

import discord

from games.images import Picture


@dataclass(frozen=True, slots=True)
class Upload:
    """Bytes to attach to a message. Files are rebuilt for every send."""

    filename: str
    data: bytes

    def file(self) -> discord.File:
        return discord.File(BytesIO(self.data), filename=self.filename)


def prepare(
    picture: Picture | None, fallback: str | None, prefix: str
) -> tuple[str | None, list[Upload]]:
    """The URL an embed should use for ``picture``, and what must be attached.

    A picture with a URL needs nothing attached. A decoded one is attached
    under a name that cannot clash with the other image of the same message.
    """
    if picture is None:
        return fallback, []
    if picture.url:
        return picture.url, []
    if picture.data:
        name = f"{prefix}_{picture.filename}"
        return f"attachment://{name}", [Upload(name, picture.data)]
    return fallback, []


def files(uploads: list[Upload]) -> list[discord.File]:
    return [upload.file() for upload in uploads]
