"""Reading ``.seq`` rhythm charts: how many notes, and how long.

Only what the bot shows is read: the note count, the length in seconds and the
number of events that are not notes. The layouts differ by game version.
"""

import base64
import binascii
import struct
from dataclasses import dataclass

# Extra bytes after some fields, by layout version.
PADDING = {0x65: 0, 0x66: 4, 0x67: 4}
# Which channels are lanes that hold notes, by chart type.
LANES = {
    0x68: range(0, 13, 4),
    0x6B: range(0, 13, 2),
    0x71: range(13),
    0x7D: range(25),
}
SLIDER_LAYOUT = 0x67


class SeqError(ValueError):
    """The data is not a chart this reader understands."""


@dataclass(frozen=True, slots=True)
class SeqStats:
    """The note count, length in seconds and invalid events of one chart."""

    count: int  # notes (a slider that holds counts twice)
    seconds: float
    invalid: int  # events that are not notes


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def take(self, fmt: str) -> int | float:
        size = struct.calcsize(fmt)
        end = self.pos + size
        if end > len(self.data):
            raise SeqError("The chart ends early.")
        value: int | float = struct.unpack_from(fmt, self.data, self.pos)[0]
        self.pos = end
        return value

    def u32(self) -> int:
        return int(self.take("<I"))

    def skip(self, size: int) -> None:
        if self.pos + size > len(self.data):
            raise SeqError("The chart ends early.")
        self.pos += size


def unwrap(data: bytes) -> bytes:
    """The chart itself: some bundles hold a chart as base64 text of the same bytes."""
    if len(data) >= 4 and struct.unpack_from("<I", data)[0] in PADDING:
        return data
    try:
        decoded = base64.b64decode(data.strip(), validate=True)
    except binascii.Error, ValueError:
        return data
    return decoded if len(decoded) >= 4 else data


def parse_seq(data: bytes) -> SeqStats:
    """Measure a chart; raise :class:`SeqError` if it cannot be read.

    Walks the header, tempo, object and channel blocks to the events and counts
    the ones that are notes.
    """
    r = _Reader(unwrap(data))
    layout = r.u32()
    if layout not in PADDING:
        raise SeqError(f"Unknown chart layout {layout:#x}.")
    pad = PADDING[layout]

    tick_length = r.u32()
    seconds = float(r.take("<d"))
    r.skip(4)  # tickPerBeat
    r.skip(pad)
    r.skip(8)  # beatPerTick
    tempo_count = r.u32()
    object_count = r.u32()
    channel_count = r.u32()
    event_count = r.u32()
    r.skip(4 + 4)  # measureCount, beatCount
    chart_type = r.u32()
    r.skip(pad)

    for _ in range(tempo_count):
        r.skip(4 + 4 + 4 + 4 + 8 + 4)  # tick .. beatPerMeasure
        r.skip(pad)
        r.skip(8 + 8 + 4)  # measurePerBeat, measurePerTick, tickPerMeasure
        r.skip(pad)
        r.skip(8 * 6 + 4 + 4)  # rates, measureStart, measureCount

    # The first object's data length comes first, its property last.
    first_length = r.u32()
    r.skip(first_length)
    for _ in range(object_count - 1):
        r.skip(4)  # property
        length = r.u32()
        r.skip(length)
    r.skip(4)  # the first object's property

    r.skip(channel_count * 8)

    lanes = LANES.get(chart_type, range(0))
    count = invalid = 0
    sliders = {"1": False, "2": False}
    for i in range(event_count):
        tick = r.u32()
        duration = r.u32()
        channel = r.u32()
        r.skip(4)  # objectId
        prop = r.u32()
        r.skip(pad)
        if not i or i == event_count - 1:
            continue  # the first and last events are markers
        if tick < tick_length and not duration and channel in lanes:
            text = str(prop)
            if layout == SLIDER_LAYOUT and len(text) > 1 and text[0] in sliders:
                match text[1]:
                    case "1" if sliders[text[0]]:
                        sliders[text[0]] = False
                        count += 2
                    case "4":
                        sliders[text[0]] = True
                    case _:
                        sliders[text[0]] = False
                        count += 1
            else:
                count += 1
        else:
            invalid += 1
    return SeqStats(count, seconds, invalid)
