"""When boxes open, what is inside them, and where.

The prizes of a day are listed under its ``MMDD`` (in KST). A prize is a role id
(a role of the guild) or a name shown as text; ``source`` is the word before it.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from discord_ids import SSRG_GUILD, TEST_GUILD


@dataclass(frozen=True, slots=True)
class Prize:
    role: int | str  # a role id of the guild, or text
    source: str = ""


CHANNELS: Mapping[int, int] = {  # guild id -> channel id
    SSRG_GUILD: 402632825834307584,
    TEST_GUILD: 1413700092418068585,
}

PRIZES: Mapping[str, tuple[Prize, ...]] = {
    "0401": (
        Prize("BTS", "SuperStar"),
        Prize("PLEDIS", "SuperStar"),
        Prize("WOOLLIM", "SUPERSTAR"),
        Prize("GFRIEND", "SuperStar"),
    ),
    "0403": (
        Prize("IZ\\*ONE", "SUPERSTAR"),
        Prize("YG", "SUPERSTAR"),
        Prize("FNC", "SUPERSTAR"),
        Prize("KANGDANIEL", "SuperStar"),
    ),
    "0404": (
        Prize("P NATION", "SUPERSTAR"),
        Prize("BRANDNEW", "SUPERSTAR"),
        Prize("THE BOYZ", "SUPERSTAR"),
        Prize("CLASS:y", "SUPERSTAR"),
    ),
    "0405": (
        Prize("OH MY GIRL", "SUPERSTAR"),
        Prize("LOOΠΔ", "SUPERSTAR"),
        Prize("BTS (JP/TW)", "SUPERSTAR"),
        Prize("PLEDIS (JP/TW)", "SUPERSTAR"),
    ),
    "0406": (
        Prize("YG (JP/TW)", "SUPERSTAR"),
        Prize("LAPONE", "SUPERSTAR"),
        Prize("The SuperStar", ""),
        Prize("THAILAND", "SUPERSTAR"),
    ),
    "0407": (Prize("全民天团", ""),),
}
