import pytest

from games.accounts import Accounts
from games.errors import ServerError
from games.ssleague import fetch_todays_song, todays_song


class Store:
    def __init__(self, data):
        self.data = data
        self.saved = []

    async def get(self, game):
        return self.data.get(game)

    async def save(self, game, fields):
        self.saved.append((game, dict(fields)))
        self.data[game] = dict(fields)


async def test_accounts_load_cache_and_save_changes():
    store = Store({"SM": {"provider": 3, "isSNS": True, "id": "a", "pass": "b"}})
    accounts = Accounts(object(), store)
    account = await accounts.get("SM")
    assert account is not None and await accounts.get("SM") is account
    await account._apply({"oid": 5, "key": "k"})  # what a login does
    assert store.saved == [
        (
            "SM",
            {
                "provider": 3,
                "isSNS": True,
                "id": "a",
                "pass": "b",
                "oid": 5,
                "key": "k",
            },
        )
    ]
    accounts.forget("SM")
    assert await accounts.get("SM") is not account


async def test_accounts_refuse_unknown_games_and_unusable_credentials():
    store = Store(
        {
            "SM": {"nope": 1},
            "SS": {"provider": 3, "isSNS": True},
            "JYP": {"provider": 7},
        }
    )
    accounts = Accounts(object(), store)
    assert await accounts.get("XX") is None  # unknown game
    assert await accounts.get("W1") is None  # no credentials
    assert await accounts.get("SM") is None  # no provider
    assert await accounts.get("JYP") is None  # no login method fits


def test_todays_song_picks_the_current_day():
    answer = {
        "result": {
            "curday": 3,
            "musicList": [{"day": 2, "music": 10}, {"day": 3, "music": "11"}],
        }
    }
    assert todays_song(answer) == 11
    assert (
        todays_song({"result": {"curday": 9, "musicList": [{"day": 1, "music": 1}]}})
        is None
    )
    assert todays_song({"result": {"curday": 1, "musicList": [{"day": 1}]}}) is None
    assert todays_song({"result": {"curday": 1, "musicList": None}}) is None
    assert todays_song({"result": None}) is None
    assert todays_song({}) is None


async def test_fetch_todays_song_uses_the_account():
    class Account:
        class game:
            key = "SM"

        def __init__(self, answer):
            self.answer = answer
            self.calls = []

        async def call(self, manifest, cls, method, *params):
            self.calls.append((cls, method, params))
            return self.answer

    ok = Account({"result": {"curday": 1, "musicList": [{"day": 1, "music": 7}]}})
    assert await fetch_todays_song(ok, "manifest") == 7
    assert ok.calls == [("StarLeague", "getWeekPlayMusic", ())]
    with pytest.raises(ServerError):
        await fetch_todays_song(Account({"result": {}}), "manifest")
