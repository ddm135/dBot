"""Small builders for fake game tables."""

import copy
import json
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from games.http import RetryPolicy

KST = ZoneInfo("Asia/Seoul")
NO_RETRY = RetryPolicy(
    attempts=1, initial=0, maximum=0, jitter=0
)  # no waiting in tests


def ms(year: int, month: int, day: int) -> int:
    return int(datetime(year, month, day, tzinfo=KST).timestamp() * 1000)


def locale(**names: str) -> dict[str, dict[str, str]]:
    return {code: {"koKR": f"ko {n}", "enUS": n} for code, n in names.items()}


class Tables:
    """Accumulates MusicData, ArtistData, GroupData and LocaleData."""

    def __init__(self) -> None:
        self.music: dict[str, dict] = {}
        self.artists: dict[str, dict] = {}
        self.groups: dict[str, dict] = {}
        self.locale: dict[str, dict] = {}
        self.urls: dict[str, dict] = {}
        self._loc = 1000

    def text(self, name: str | None) -> int | None:
        if name is None:
            return None
        self._loc += 1
        self.locale[str(self._loc)] = {"koKR": f"ko {name}", "enUS": name}
        return self._loc

    def group(self, code: int, name: str, **extra: object) -> None:
        self.groups[str(code)] = {
            "code": code,
            "localeName": self.text(name),
            "analyticsData": name,
            **extra,
        }

    def artist(
        self,
        code: int,
        name: str,
        group: int,
        birthday: tuple[int, int, int] | None = (2000, 5, 10),
        use: bool = True,
        **extra: object,
    ) -> None:
        self.artists[str(code)] = {
            "code": code,
            "localeName": self.text(name),
            "group": group,
            "bonusBirthday": ms(*birthday) if birthday else None,
            "bonusBirthdayUse": use,
            **extra,
        }

    def song(
        self,
        code: int,
        name: str,
        deck: int,
        release: tuple[int, int, int] = (2020, 1, 1),
        artists: list[int] | None = None,
        hidden: bool = False,
        **extra: object,
    ) -> None:
        import json

        self.music[str(code)] = {
            "code": code,
            "localeName": self.text(name),
            "analyticsData": name,
            "groupData": deck,
            "releaseDate": ms(*release),
            "artistCode": json.dumps(artists or []),
            "isHidden": hidden,
            **extra,
        }

    def as_tables(self) -> dict[str, dict[str, dict]]:
        tables = {
            "MusicData": self.music,
            "ArtistData": self.artists,
            "GroupData": self.groups,
            "LocaleData": self.locale,
        }
        if self.urls:
            tables["URLs"] = self.urls
        return tables


def d(y: int, m: int, day: int) -> date:
    return date(y, m, day)


class MemoryStats:
    """The song stats table, in memory (what ``SongStatsDb`` is, without Postgres)."""

    def __init__(self, songs: dict[str, dict[str, Any]] | None = None) -> None:
        self.songs = {game: copy.deepcopy(docs) for game, docs in (songs or {}).items()}
        self.versions = dict.fromkeys(self.songs, 1)
        self.loads = 0

    async def version(self, game: str) -> int:
        return self.versions.get(game, 0)

    async def load(self, game: str) -> dict[str, Any]:
        self.loads += 1
        return copy.deepcopy(self.songs.get(game, {}))

    async def save(self, game: str, songs: Any) -> int:
        new = json.loads(json.dumps(songs))
        if new == self.songs.get(game):
            return 0
        self.songs[game] = new
        self.versions[game] = self.versions.get(game, 0) + 1
        return len(new)
