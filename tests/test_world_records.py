from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import httpx
import pytest
from discord import app_commands

from cogs.world_record import WorldRecord, season_autocomplete
from games.api.world_records import (
    Leaderboard,
    Record,
    WorldRecordError,
    WorldRecords,
    parse_last_modified,
    parse_records,
)
from games.bonus.schedule import (
    SeasonError,
    check_weekly,
    current_monday,
    latest_season,
    quarterly_seasons,
    season_code_of,
)
from games.registry import GAMES
from ui.world_record import (
    artist_embed,
    last_updated_text,
    leaderboard_embed,
    page_total,
)

from .data import KST, NO_RETRY, Tables
from .test_commands import Itr, Sent  # noqa: F401
from .test_index_search import FakeService

SM = GAMES["SM"]
W1 = GAMES["W1"]
BASE = "https://rank.example/"


def ms(y, m, d):
    return int(datetime(y, m, d, tzinfo=KST).timestamp() * 1000)


# --- seasons ------------------------------------------------------------------------


def season_tables():
    rows = {}
    code = 1
    for season, (start, end) in enumerate(
        [
            ((2020, 1, 1), (2020, 3, 31)),
            ((2020, 4, 1), (2020, 6, 30)),
            ((2020, 7, 1), (2020, 9, 30)),
            ((2099, 10, 1), (2099, 12, 31)),
        ],
        1,
    ):
        for tier in range(3):  # a row per reward tier
            rows[str(code)] = {
                "seasonCode": season,
                "startAt": ms(*start),
                "endAt": ms(*end),
            }
            code += 1
    return {"WorldRecordData": rows}


def test_only_started_seasons_are_listed_once_each_oldest_first():
    now = datetime(2026, 8, 15, tzinfo=KST)
    seasons = quarterly_seasons(season_tables(), KST, now)
    assert list(seasons) == [1, 2, 3]  # season 4 has not started
    assert seasons[3].start == datetime(2020, 7, 1, tzinfo=KST)
    assert seasons[3].end == datetime(2020, 9, 30, tzinfo=KST)
    assert latest_season(seasons) == 3 and latest_season({}) is None
    assert quarterly_seasons({}, KST, now) == {}


def test_malformed_season_rows_are_skipped():
    bad = {
        "WorldRecordData": {
            "1": {"seasonCode": "x", "startAt": 1, "endAt": 2},
            "2": {"seasonCode": 5, "startAt": None, "endAt": 2},
            "3": {"seasonCode": 6, "startAt": True, "endAt": 2},
            "4": {"seasonCode": 7, "startAt": 0, "endAt": 1000},
        }
    }
    assert list(quarterly_seasons(bad, KST, datetime(2026, 1, 1, tzinfo=KST))) == [7]


def test_weekly_season_codes():
    assert season_code_of(date(2024, 12, 2)) == 20241202
    assert current_monday(date(2026, 10, 25)) == date(2026, 10, 19)
    first, today = date(2024, 12, 2), date(2026, 10, 25)
    assert check_weekly(20260921, first, today) == date(2026, 9, 21)
    for code, message in [
        (20260922, "Monday"),
        (20261026, "future"),
        (20241125, "before"),
        (20261340, "YYYYMMDD"),
    ]:
        with pytest.raises(SeasonError, match=message):
            check_weekly(code, first, today)
    assert check_weekly(20241202, first, today) == first  # the first season itself


# --- the rank server -------------------------------------------------------------------


def records_json(n=3):
    return [
        {"rank": i + 1, "nickname": f"p{i}", "highscore": 1_000_000 - i}
        for i in range(n)
    ]


def server(routes):
    """routes: {path: (status, body, headers)}"""
    seen = []

    def handler(request):
        seen.append(request.url.path)
        status, body, headers = routes.get(request.url.path, (404, None, {}))
        return httpx.Response(status, json=body, headers=headers)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), seen


def test_records_are_parsed_leniently():
    assert parse_records(records_json(2)) == (
        Record(1, "p0", 1_000_000),
        Record(2, "p1", 999_999),
    )
    assert parse_records([{"nickname": "solo", "highscore": 5}]) == (
        Record(1, "solo", 5),
    )
    assert parse_records([{"nickname": 1, "highscore": 5}, "x", {"highscore": 1}]) == ()
    assert parse_records({"not": "a list"}) == ()


def test_last_modified_is_shown_in_the_games_timezone():
    got = parse_last_modified("Mon, 05 Oct 2026 19:03:09 GMT", KST)
    assert got == datetime(2026, 10, 6, 4, 3, 9, tzinfo=KST)
    assert (
        parse_last_modified(None, KST) is None
        and parse_last_modified("junk", KST) is None
    )


async def test_the_full_board_is_preferred_and_the_time_is_read():
    client, seen = server(
        {
            "/10/7/latest.json": (
                200,
                records_json(),
                {"Last-Modified": "Mon, 05 Oct 2026 19:03:09 GMT"},
            )
        }
    )
    async with client:
        board = await WorldRecords(client, retry=NO_RETRY).fetch(BASE, 10, 7, KST)
    assert [r.nickname for r in board.records] == ["p0", "p1", "p2"]
    assert board.updated == datetime(2026, 10, 6, 4, 3, 9, tzinfo=KST)
    assert seen == ["/10/7/latest.json"]


async def test_it_falls_back_to_the_leader_only_board_and_then_to_nothing():
    client, seen = server({"/10/7/latest_first.json": (200, records_json(1), {})})
    async with client:
        wr = WorldRecords(client, retry=NO_RETRY)
        board = await wr.fetch(BASE, 10, 7, KST)
        assert len(board.records) == 1 and board.updated is None
        assert seen == ["/10/7/latest.json", "/10/7/latest_first.json"]
        assert await wr.fetch(BASE, 10, 8, KST) == Leaderboard()  # nobody has played
        first_only = await wr.fetch(BASE, 10, 7, KST, first_only=True)
        assert len(first_only.records) == 1
    # The leader-only request was answered from what was already fetched.
    assert seen.count("/10/7/latest.json") == 1


async def test_a_base_url_with_or_without_a_slash_works():
    client, seen = server({"/10/7/latest.json": (200, records_json(), {})})
    async with client:
        await WorldRecords(client, retry=NO_RETRY).fetch(
            "https://rank.example", 10, 7, KST
        )
    assert seen == ["/10/7/latest.json"]


async def test_server_trouble_is_an_error_not_an_empty_board():
    client, _ = server(
        {"/1/1/latest.json": (500, None, {}), "/1/2/latest.json": (200, None, {})}
    )
    async with client:
        wr = WorldRecords(client, retry=NO_RETRY)
        with pytest.raises(WorldRecordError):
            await wr.fetch(BASE, 1, 1, KST)
    broken = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, content=b"not json")
        )
    )
    async with broken:
        with pytest.raises(WorldRecordError):
            await WorldRecords(broken, retry=NO_RETRY).fetch(BASE, 1, 1, KST)

    def refuse(request):
        raise httpx.ConnectError("down")

    async with httpx.AsyncClient(transport=httpx.MockTransport(refuse)) as down:
        with pytest.raises(WorldRecordError):
            await WorldRecords(down, retry=NO_RETRY).fetch(BASE, 1, 1, KST)


async def test_boards_are_cached_briefly():
    client, seen = server({"/10/7/latest.json": (200, records_json(), {})})
    now = [0.0]
    async with client:
        wr = WorldRecords(client, retry=NO_RETRY, clock=lambda: now[0], ttl=60)
        await wr.fetch(BASE, 10, 7, KST)
        await wr.fetch(BASE, 10, 7, KST)
        assert len(seen) == 1
        now[0] += 61
        await wr.fetch(BASE, 10, 7, KST)
        assert len(seen) == 2


async def test_fetch_many_reports_failures_per_item():
    client, _ = server(
        {
            "/10/1/latest_first.json": (200, records_json(1), {}),
            "/10/3/latest_first.json": (500, None, {}),
        }
    )
    async with client:
        results = await WorldRecords(client, retry=NO_RETRY).fetch_many(
            BASE, 10, [1, 2, 3], KST, first_only=True
        )
    assert (
        isinstance(results[1], Leaderboard) and results[1].records[0].nickname == "p0"
    )
    assert results[2] == Leaderboard()  # nobody has played it
    assert isinstance(results[3], WorldRecordError)


# --- embeds ------------------------------------------------------------------------------


def test_the_leaderboard_embed_matches_v0():
    records = tuple(Record(i, f"n*{i}", 1_000 * i) for i in range(1, 13))
    updated = datetime(2026, 10, 5, 4, 3, 9, tzinfo=KST)
    embed = leaderboard_embed(
        SM,
        "TW_ICE",
        "Cheer *Up*",
        27,
        records,
        updated,
        "http://album",
        "http://icon",
        page=2,
    )
    assert embed.title == "TW\\_ICE - Cheer \\*Up\\*"
    assert embed.description == "11. **n\\*11** - 11,000\n12. **n\\*12** - 12,000"
    assert embed.author.name == f"{SM.name} - World Record (Season 27)"
    assert (
        embed.footer.text
        == "Page 2/2 · Last Updated: Monday, October 5, 2026, 4:03:09 KST"
    )
    assert embed.thumbnail.url == "http://album" and embed.color.value == SM.color
    assert (
        leaderboard_embed(SM, "A", None, 1, (), None, None, None).description == "None"
    )
    assert leaderboard_embed(SM, "A", None, 1, (), None, None, None).title == "A"
    assert (
        leaderboard_embed(SM, "A", None, 1, (), None, None, None).footer.text
        == "Page 1/1"
    )


def test_the_artist_embed_lists_each_songs_leader():
    rows = [
        ("Cheer Up", Record(1, "top", 5_000)),
        ("Fancy", "None"),
        ("Alcohol_Free", "Error"),
    ]
    embed = artist_embed(SM, "TWICE", 27, rows, None, None)
    assert embed.title == "TWICE"
    assert embed.description == (
        "- Cheer Up: **top** - 5,000\n- Fancy: **None**\n- Alcohol\\_Free: **Error**"
    )
    assert artist_embed(SM, "A", 1, [], None, None).description == "None"
    assert page_total(0) == 1 and page_total(10) == 1 and page_total(11) == 2


def test_the_footer_time_drops_leading_zeros_as_v0_did():
    assert last_updated_text(None) == ""
    got = last_updated_text(datetime(2026, 10, 5, 5, 3, 9, tzinfo=KST))
    assert got == " · Last Updated: Monday, October 5, 2026, 5:03:09 KST"


# --- the commands ----------------------------------------------------------------------------


def choice(game):
    return app_commands.Choice(name=GAMES[game].name, value=game)


def world(rank_url=BASE, season_rows=True):
    t = Tables()
    t.group(1, "TWICE")
    t.group(2, "BTS")
    t.song(10, "Cheer Up", 1)
    t.song(11, "Fancy", 1)
    t.song(12, "Hidden", 1, hidden=True)
    t.song(20, "Dynamite", 2)
    tables = t.as_tables()
    if season_rows:
        tables.update(season_tables())
    return tables, rank_url


async def make_bot(tmp_path, tables, rank_url, routes, game="SM"):
    from games.index import Indexes
    from search import Searcher  # noqa: F401

    service = FakeService(tables)
    service.data.manifest = SimpleNamespace(music_rank_server_url=rank_url)
    service.data.icon_url = "http://game-icon"
    indexes = Indexes(service)
    client, seen = server(routes)

    class Images:
        async def emblem(self, g, d):
            return None

        async def album(self, g, s):
            return None

    bot = SimpleNamespace(
        indexes=indexes,
        games=service,
        images=Images(),
        world_records=WorldRecords(client, retry=NO_RETRY),
    )
    return bot, client, seen


async def test_a_songs_top_100_is_shown_with_pages(tmp_path):
    tables, url = world()
    routes = {"/3/10/latest.json": (200, records_json(25), {})}
    bot, client, _ = await make_bot(tmp_path, tables, url, routes)
    async with client:
        itr = Itr()
        await WorldRecord.quarterly.callback(
            WorldRecord(bot), itr, choice("SM"), "1", "10", None
        )
    embed = itr.last[1]["embed"]
    assert (
        embed.title == "TWICE - Cheer Up" and "Season 3" in embed.author.name
    )  # the latest started
    assert embed.footer.text == "Page 1/3"
    assert embed.description.splitlines()[0] == "1. **p0** - 1,000,000"
    assert itr.last[1]["view"] is not None


async def test_an_artists_top_one_per_song_hides_hidden_songs(tmp_path):
    tables, url = world()
    routes = {
        "/2/10/latest_first.json": (
            200,
            records_json(1),
            {"Last-Modified": "Mon, 05 Oct 2026 19:03:09 GMT"},
        ),
        "/2/11/latest_first.json": (500, None, {}),
    }
    bot, client, seen = await make_bot(tmp_path, tables, url, routes)
    async with client:
        itr = Itr()
        await WorldRecord.quarterly.callback(
            WorldRecord(bot), itr, choice("SM"), "1", None, 2
        )
    embed = itr.last[1]["embed"]
    assert embed.description == "- Cheer Up: **p0** - 1,000,000\n- Fancy: **Error**"
    assert "Last Updated" in embed.footer.text
    assert not any("/12/" in p for p in seen)  # the hidden song was never asked about


async def test_quarterly_rejects_unknown_input(tmp_path):
    tables, url = world()
    bot, client, _ = await make_bot(tmp_path, tables, url, {})
    async with client:
        for args, text in [
            (("99", None, None), "Artist not found."),
            (("1", "20", None), "Song not found."),  # a song of another artist
            (("1", None, 4), "Season not found."),  # has not started
            (("1", None, 77), "Season not found."),
        ]:
            itr = Itr()
            await WorldRecord.quarterly.callback(
                WorldRecord(bot), itr, choice("SM"), *args
            )
            assert itr.last[0] == text
        bot.games.data.manifest = SimpleNamespace(music_rank_server_url=None)
        itr = Itr()
        await WorldRecord.quarterly.callback(
            WorldRecord(bot), itr, choice("SM"), "1", None, None
        )
        assert "not available" in itr.last[0]


async def test_a_dead_rank_server_is_reported(tmp_path):
    tables, url = world()
    bot, client, _ = await make_bot(
        tmp_path, tables, url, {"/3/10/latest.json": (500, None, {})}
    )
    async with client:
        itr = Itr()
        await WorldRecord.quarterly.callback(
            WorldRecord(bot), itr, choice("SM"), "1", "10", None
        )
    assert "could not be reached" in itr.last[0]


async def test_weekly_defaults_to_this_monday_and_checks_the_code(tmp_path):
    tables, url = world(season_rows=False)
    monday = season_code_of(current_monday(W1.now().date()))
    routes = {f"/{monday}/1/latest.json": (200, records_json(2), {})}
    bot, client, _ = await make_bot(tmp_path, tables, url, routes)
    async with client:
        itr = Itr()
        await WorldRecord.weekly.callback(
            WorldRecord(bot), itr, choice("W1"), "1", None
        )
        embed = itr.last[1]["embed"]
        assert embed.title == "TWICE" and f"Season {monday}" in embed.author.name
        for code, text in [
            (20260922, "Monday"),
            (20991228, "future"),
            (20241125, "before"),
        ]:
            itr = Itr()
            await WorldRecord.weekly.callback(
                WorldRecord(bot), itr, choice("W1"), "1", code
            )
            assert text in itr.last[0]
        itr = Itr()
        await WorldRecord.weekly.callback(
            WorldRecord(bot), itr, choice("W1"), "99", None
        )
        assert itr.last[0] == "Artist not found."


async def test_season_choices_are_newest_first_and_filtered():
    tables, _ = world()
    service = FakeService(tables)
    itr = SimpleNamespace(
        namespace=SimpleNamespace(game="SM"), client=SimpleNamespace(games=service)
    )
    choices = await season_autocomplete(itr, "")
    assert [c.value for c in choices] == [3, 2, 1]  # season 4 has not started
    assert choices[0].name.startswith("Season 3 (")
    assert [c.value for c in await season_autocomplete(itr, "3")] == [3]
    assert (
        await season_autocomplete(
            SimpleNamespace(namespace=SimpleNamespace(game=None), client=None), ""
        )
        == []
    )


def test_games_are_split_into_quarterly_and_weekly():
    assert GAMES["W1"].has_weekly_seasons and not GAMES["W1"].has_quarterly_seasons
    assert GAMES["SM"].has_quarterly_seasons and not GAMES["BL"].has_quarterly_seasons
    assert ZoneInfo("Asia/Seoul") == KST
