"""Template strings (PEP 750): interpolations are quoted by the function that renders them."""

from collections.abc import Callable
from string.templatelib import Template, convert


class Raw(str):
    """Text a template inserts as it is, already safe for where it goes."""


def render(template: Template, quote: Callable[[str], str]) -> str:
    """Join a template, passing every interpolated value through ``quote``.

    The literal parts are the author's own and stay as written. ``Raw`` values
    skip ``quote``; a format spec and conversion apply as in an f-string.
    """
    parts: list[str] = []
    for part in template:
        if isinstance(part, str):
            parts.append(part)
            continue
        text = format(convert(part.value, part.conversion), part.format_spec)
        parts.append(text if isinstance(part.value, Raw) else quote(text))
    return "".join(parts)
