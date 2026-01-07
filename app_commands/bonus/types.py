from datetime import datetime
from typing import TypedDict


class BonusDict(TypedDict):
    artist: str
    members: str | None
    song: str | None
    bonusStart: datetime
    bonusEnd: datetime
    bonusAmount: int
    maxScore: int | None
