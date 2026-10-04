from datetime import date

from db.legacy import (
    Report,
    import_all,
    parse_live_themes,
    parse_notify_bonus,
    parse_roles,
    parse_ssleagues,
    parse_word_pings,
)

GAMES = {"SM", "JYP"}


def test_word_pings_merge_case_and_skip_empty_entries():
    data = {
        "1": {
            "Cat": {"10": {"users": [5], "channels": [7], "count": 2}, "11": {}},
            "cat": {"10": {"users": ["6"], "channels": [], "count": 3}},
            "": {"10": {"users": [], "channels": [], "count": 1}},
        },
        "bad": {"x": {}},
    }
    result = parse_word_pings(data)
    assert set(result) == {(1, 10, "cat")}
    ping = result[(1, 10, "cat")]
    assert (ping.count, ping.users, ping.channels) == (5, {5, 6}, {7})


def test_roles_and_live_themes_in_either_layout():
    assert parse_roles({"1": [2, "3"], "x": [1], "2": "no"}) == {(1, 2), (1, 3)}
    assert parse_live_themes({"10": {"SM": 5, "XX": 9}}, GAMES) == {(10, "SM"): 5}
    assert parse_live_themes({"SM": {"10": 5, "11": 0}}, GAMES) == {(10, "SM"): 5}


def test_notify_bonus_prefers_requested_hours_and_reports_unknown_artists():
    report = Report()
    data = {
        "SM": {
            "TWICE": [1, 2],
            "Nobody": [3],
            "Nobody Else": [4],
            "start": {},
            "reend": [1],
        },
        "1": {"start": [2], "end": [1], "restart": [5], "reend": [0]},
        "2": {"start": [30]},
        "x": "ignored",
    }
    result = parse_notify_bonus(
        data, GAMES, lambda g, a: 9 if a == "TWICE" else None, report
    )
    assert result.subscriptions == {(1, "SM", 9), (2, "SM", 9)}
    assert result.preferences == {1: (5, 0), 2: (23, 1)}
    # v0's leftover keys are ignored, and unknown names are reported once per game.
    assert report.skipped == ["bonus pings: SM: no deck named 'Nobody', 'Nobody Else'"]


def test_ssleagues_become_one_row_per_day():
    report = Report()
    data = {
        "SM": {
            "TWICE": {
                "date": "2025-01-02",
                "songs": {"1": "2025-01-01", "2": "2025-01-02", "9": None},
            },
            "Gone": {"songs": {"5": "2025-01-03"}},
        }
    }
    rows = parse_ssleagues(
        data,
        lambda g, a: 10 if a == "TWICE" else None,
        lambda g, s: 20 if s == 5 else None,
        lambda g, text: date.fromisoformat(text),
        report,
    )
    assert rows == {
        ("SM", date(2025, 1, 1)): (1, 10),
        ("SM", date(2025, 1, 2)): (2, 10),
        ("SM", date(2025, 1, 3)): (5, 20),
    }


async def test_import_all_writes_everything_and_is_repeatable(database):
    v0 = {
        "credentials": {"SM": {"provider": 3, "isSNS": True}, "XX": {"provider": 1}},
        "word_pings": {
            "1": {"cat": {"10": {"users": [5], "channels": [7], "count": 4}}}
        },
        "roles": {"10": [100, 200]},
        "live_theme": {"10": {"SM": 1500}},
        "notify_bonus": {"SM": {"TWICE": [10]}, "10": {"start": [3], "end": [2]}},
        "ssleagues": {"SM": {"TWICE": {"songs": {"1": "2025-01-01"}}}},
    }
    args = {
        "games": GAMES,
        "deck_of": lambda g, a: 9,
        "deck_of_song": lambda g, s: 9,
        "parse_date": lambda g, t: date.fromisoformat(t),
    }
    first = await import_all(database.pool, v0, **args)
    second = await import_all(database.pool, v0, **args)
    assert first.imported == second.imported
    assert first.imported["credentials"] == 1 and first.imported["stored roles"] == 2

    assert await database.credentials.get("SM") == {"provider": 3, "isSNS": True}
    assert await database.credentials.get("XX") is None
    await database.word_pings.load()
    sub = database.word_pings.get(1, 10, "cat")
    assert (sub.count, sub.users, sub.channels) == (4, {5}, {7})
    assert await database.roles.get(10) == {100, 200}
    assert await database.live_themes.get(10, "SM") == 1500
    assert await database.bonus_pings.decks_of(10, "SM") == [9]
    prefs = (await database.bonus_pings.preferences([10]))[10]
    assert (prefs.start_hours, prefs.end_hours) == (3, 2)
    assert (await database.ssl.last("SM", 1, 9)).song == date(2025, 1, 1)
