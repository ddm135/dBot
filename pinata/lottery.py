"""Who has lined up for which prize, and the draw for a prize.

Pure logic: the entrants are whatever the caller uses to tell users apart.
"""

import random
from collections.abc import Hashable, Iterator, Sequence
from dataclasses import dataclass

MIN_ROLL_SUPERSTAR = 99.5  # a SuperStar role is harder to win than it sounds
MIN_ROLL_OTHER = 99.99


def min_roll(is_superstar: bool) -> float:
    return MIN_ROLL_SUPERSTAR if is_superstar else MIN_ROLL_OTHER


def roll(rng: random.Random) -> float:
    """0.00 to 100.00 in steps of 0.01."""
    return rng.randint(0, 10_000) / 100


class Entries[T: Hashable]:
    """For each entrant, which prizes (by position) they are lined up for."""

    def __init__(self, prizes: int) -> None:
        self.prizes = prizes
        self._flags: dict[T, list[bool]] = {}

    def __bool__(self) -> bool:
        return bool(self._flags)

    def __iter__(self) -> Iterator[tuple[T, list[bool]]]:
        return iter(self._flags.items())

    def join_all(self, who: T) -> None:
        self._flags[who] = [True] * self.prizes

    def leave_all(self, who: T) -> None:
        self._flags.pop(who, None)

    def toggle(self, who: T, prize: int) -> None:
        """Line up for one prize, or leave its line; nobody is left with none."""
        flags = self._flags.setdefault(who, [False] * self.prizes)
        flags[prize] = not flags[prize]
        if not any(flags):
            del self._flags[who]

    def for_prize(self, prize: int) -> list[T]:
        """The entrants for a prize, in the order they first lined up."""
        return [who for who, flags in self._flags.items() if flags[prize]]


@dataclass(frozen=True, slots=True)
class Draw[T]:
    rolls: tuple[tuple[T, float], ...]  # in line order
    winner: T | None  # the first to reach the minimum
    minimum: float
    rolls_needed: int  # with no winner: how many rolls it would have taken


def draw[T](entrants: Sequence[T], minimum: float, rng: random.Random) -> Draw[T]:
    rolls = tuple((who, roll(rng)) for who in entrants)
    winner = next((who for who, value in rolls if value >= minimum), None)
    needed = 0
    if winner is None:
        value = 0.0
        while value < minimum:
            value = roll(rng)
            needed += 1
    return Draw(rolls, winner, minimum, needed)
