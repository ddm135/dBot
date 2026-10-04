"""Score ceilings per deck: member counts, base score, live-theme maximum."""

from collections.abc import Collection, Mapping
from dataclasses import dataclass

from .decks import Entry, Tables

PER_MEMBER = 15_000
BASE_MEMBERS = 3
EXCLUDED_ARTIST_TYPE = 4


@dataclass(frozen=True, slots=True)
class DeckScore:
    member_count: int
    base: int  # 0 when the game has no known base score


def member_counts(artists: Mapping[str, Entry]) -> dict[int, int]:
    """Members per deck: artists of the deck that are not of type 4."""
    counts: dict[int, int] = {}
    for artist in artists.values():
        if artist.get("artistType", 1) == EXCLUDED_ARTIST_TYPE:
            continue
        try:
            group = int(artist["group"])
        except KeyError, TypeError, ValueError:
            continue
        counts[group] = counts.get(group, 0) + 1
    return counts


def deck_scores(
    tables: Tables, base_score: int | None, deck_codes: list[int]
) -> dict[int, DeckScore]:
    counts = member_counts(tables.get("ArtistData", {}))
    scores: dict[int, DeckScore] = {}
    for code in deck_codes:
        members = counts.get(code, 0)
        base = base_score + PER_MEMBER * (members - BASE_MEMBERS) if base_score else 0
        scores[code] = DeckScore(members, base)
    return scores


def live_theme_maximum(
    tables: Tables, counts: Mapping[int, int], deck_codes: Collection[int]
) -> int:
    """The most live-theme score a player can have, or 0 if the game has none.

    Only games whose ``LiveThemeData`` has ``collectRewardID`` count it, and
    only themes of the given decks add to it.
    """
    themes = tables.get("LiveThemeData", {})
    if not themes or "collectRewardID" not in next(iter(themes.values())):
        return 0
    total = 0
    for theme in themes.values():
        try:
            group = int(theme["groupID"])
        except KeyError, TypeError, ValueError:
            continue
        if group not in deck_codes:
            continue
        total += PER_MEMBER * counts.get(group, 0)
    return total
