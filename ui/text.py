"""Small text helpers shared by embeds."""

from datetime import date, datetime

MARKDOWN_CHARS = ("*", "_", "`")  # the same three v0 escaped


def escape(text: str) -> str:
    """Escape the markdown characters that appear in names (as v0 did)."""
    for char in MARKDOWN_CHARS:
        text = text.replace(char, f"\\{char}")
    return text


def month_day(value: date | datetime) -> str:
    """``June 7``: the month and day without a leading zero."""
    return f"{value:%B} {value.day}"


def long_date(value: date | datetime) -> str:
    """``Monday, June 7, 2021``."""
    return f"{value:%A}, {value:%B} {value.day}, {value.year}"


def timestamp(value: datetime, style: str = "R") -> str:
    """A Discord timestamp such as ``<t:1700000000:R>``."""
    return f"<t:{int(value.timestamp())}:{style}>"


def truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"
