from datetime import date

import pytest

from db import migrate
from db.bonus_pings import PingPreferences
from db.migrations import MIGRATIONS
from db.word_pings import WordPings, normalize, word_pattern

G, U, U2 = 1, 10, 20


def test_word_pattern_needs_boundaries_and_ignores_case():
    p = word_pattern("cat")
    assert p.search("my CAT sat")
    assert p.search("cat")
    assert p.search("(cat)")
    assert p.search("hi, cat!")
    assert not p.search("concatenate")
    assert not p.search("cats")
    assert word_pattern("c++").search("i like c++ a lot")  # escaped


def test_normalize():
    assert normalize("  Hello   World ") == "hello world"


async def test_migrate_is_idempotent(database):
    assert await migrate(database.pool) == []
    async with database.pool.acquire() as conn:
        versions = [
            r["version"]
            for r in await conn.fetch("SELECT version FROM schema_migrations")
        ]
    assert versions == [v for v, _ in MIGRATIONS]


# --- word pings -------------------------------------------------------------


async def test_add_remove_and_reload(database):
    wp = database.word_pings
    assert await wp.add(G, U, "Cat")
    assert not await wp.add(G, U, "cat")  # same word, any case
    assert await wp.add(G, U2, "cat")
    assert set(wp.words_of(G, U)) == {"cat"}

    again = WordPings(database.pool)
    await again.load()
    assert set(again.words_of(G, U)) == {"cat"}
    assert set(again.words_of(G, U2)) == {"cat"}

    assert await wp.remove(G, U, "CAT")
    assert not await wp.remove(G, U, "cat")
    assert wp.get(G, U2, "cat") is not None  # the other user keeps it


async def test_invalid_words_are_refused(database):
    with pytest.raises(ValueError):
        await database.word_pings.add(G, U, "   ")
    with pytest.raises(ValueError):
        await database.word_pings.add(G, U, "x" * 101)


async def test_matches_and_counts_persist(database):
    wp = database.word_pings
    await wp.add(G, U, "cat")
    await wp.add(G, U2, "cat")
    await wp.add(G, U, "dog")
    await wp.add(2, U, "bird")  # another guild

    found = dict(wp.matches(G, "the Cat and the dog"))
    assert set(found) == {"cat", "dog"}
    assert set(found["cat"]) == {U, U2}
    assert wp.matches(G, "nothing") == []
    assert wp.matches(2, "cat") == []

    await wp.record_ping(G, U, "cat")
    await wp.record_ping(G, U, "cat")
    await wp.record_ping(G, U, "missing")  # no error
    again = WordPings(database.pool)
    await again.load()
    assert again.get(G, U, "cat").count == 2


async def test_ignore_one_word_or_all(database):
    wp = database.word_pings
    await wp.add(G, U, "cat")
    await wp.add(G, U, "dog")
    await wp.add(G, U2, "cat")

    assert await wp.ignore(G, U, "user", 99, "cat") == 1
    assert await wp.ignore(G, U, "user", 99, "cat") == 0  # already
    assert await wp.ignore(G, U, "user", 99) == 1  # only dog is left to change
    assert await wp.ignore(G, U, "channel", 7) == 2
    assert await wp.ignore(G, U, "user", 5, "missing") == 0

    sub = wp.get(G, U, "cat")
    assert sub.ignores(99, 0) and sub.ignores(0, 7) and not sub.ignores(1, 1)
    assert not wp.get(G, U2, "cat").ignores(99, 7)  # other users unaffected

    again = WordPings(database.pool)
    await again.load()
    assert again.get(G, U, "dog").users == {99}
    assert again.get(G, U, "dog").channels == {7}

    assert await wp.unignore(G, U, "user", 99) == 2
    assert await wp.unignore(G, U, "user", 99) == 0
    assert await wp.unignore(G, U, "channel", 7, "cat") == 1
    assert wp.get(G, U, "cat").channels == set()
    assert wp.get(G, U, "dog").channels == {7}


async def test_removing_a_word_removes_its_ignores(database):
    wp = database.word_pings
    await wp.add(G, U, "cat")
    await wp.ignore(G, U, "user", 99)
    await wp.remove(G, U, "cat")
    await wp.add(G, U, "cat")
    again = WordPings(database.pool)
    await again.load()
    assert again.get(G, U, "cat").users == set()
    async with database.pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM word_ping_ignores") == 0


# --- roles --------------------------------------------------------------------


async def test_stored_roles(database):
    roles = database.roles
    assert await roles.get(U) == set()
    await roles.add(U, [1, 2, 3])
    await roles.add(U, [3])  # no error on duplicates
    assert await roles.get(U) == {1, 2, 3}
    await roles.change(U, add=[9], remove=[1, 2])
    assert await roles.get(U) == {3, 9}
    await roles.remove(U, [])
    assert await roles.get(U2) == set()


# --- ssl ------------------------------------------------------------------------


async def test_ssl_last_appearances(database):
    ssl = database.ssl
    empty = await ssl.last("SM", 1, 5)
    assert (empty.song, empty.deck) == (None, None)

    await ssl.record("SM", date(2025, 1, 1), 1, 5)
    await ssl.record("SM", date(2025, 1, 2), 2, 5)
    await ssl.record("SM", date(2025, 1, 3), 1, 5)
    await ssl.record("JYP", date(2025, 1, 4), 1, 5)  # another game

    last = await ssl.last("SM", 2, 5)
    assert (last.song, last.deck) == (date(2025, 1, 2), date(2025, 1, 3))
    before = await ssl.last("SM", 1, 5, before=date(2025, 1, 3))
    assert (before.song, before.deck) == (date(2025, 1, 1), date(2025, 1, 2))

    await ssl.record("SM", date(2025, 1, 3), 7, 6)  # same day replaces
    assert (await ssl.last("SM", 1, 5)).song == date(2025, 1, 1)

    assert await ssl.pinned_on("SM", date(2025, 1, 3))
    assert not await ssl.pinned_on("SM", date(2025, 1, 9))


# --- bonus pings --------------------------------------------------------------


async def test_bonus_subscriptions_and_preferences(database):
    bp = database.bonus_pings
    assert await bp.subscribe(U, "SM", 5)
    assert not await bp.subscribe(U, "SM", 5)
    assert await bp.subscribe(U, "SM", 6)
    assert await bp.subscribe(U2, "SM", 5)
    assert await bp.subscribe(U, "JYP", 1)
    assert await bp.decks_of(U, "SM") == [5, 6]
    assert await bp.subscribers("SM") == {U: {5, 6}, U2: {5}}

    assert await bp.unsubscribe(U, "SM", 6)
    assert not await bp.unsubscribe(U, "SM", 6)

    prefs = await bp.preferences([U, 12345])
    assert prefs == {U: PingPreferences(1, 1), 12345: PingPreferences(1, 1)}
    assert await bp.preferences([]) == {}

    assert await bp.set_preferences(U, start_hours=3) == PingPreferences(3, 1)
    assert await bp.set_preferences(U, end_hours=0) == PingPreferences(3, 0)
    assert await bp.set_preferences(777, end_hours=5) == PingPreferences(1, 5)
    assert PingPreferences(3, 0).hours("start") == 3
    assert PingPreferences(3, 0).hours("end") == 0


async def test_ping_log_claims_once_and_prunes(database):
    bp = database.bonus_pings
    day = date(2025, 6, 1)
    assert await bp.claim(U, "SM", day, "start")
    assert not await bp.claim(U, "SM", day, "start")
    assert await bp.claim(U, "SM", day, "end")
    await bp.release(U, "SM", day, "start")
    assert await bp.claim(U, "SM", day, "start")

    assert await bp.prune(date(2025, 6, 10)) == 0
    assert await bp.prune(date(2025, 6, 30)) == 2
    assert await bp.claim(U, "SM", day, "start")


# --- misc -----------------------------------------------------------------------


async def test_live_themes(database):
    lt = database.live_themes
    assert await lt.get(U, "SM") == 0
    await lt.set(U, "SM", 1500)
    await lt.set(U, "SM", 2500)
    assert await lt.get(U, "SM") == 2500
    assert await lt.get(U, "JYP") == 0


async def test_credentials_round_trip_json(database):
    cr = database.credentials
    assert await cr.get("SM") is None
    fields = {"provider": 3, "isSNS": True, "id": 'a"b', "nested": {"x": [1, 2]}}
    await cr.save("SM", fields)
    assert await cr.get("SM") == fields
    await cr.save("SM", {**fields, "key": "k"})
    assert (await cr.all())["SM"]["key"] == "k"
    assert await cr.delete("SM")
    assert not await cr.delete("SM")


async def test_aliases_are_lowercase_and_grouped(database):
    al = database.aliases
    assert await al.add("SM", "song", 1, "  Hello ")
    assert not await al.add("SM", "song", 1, "hello")
    await al.add("SM", "song", 1, "annyeong")
    await al.add("SM", "deck", 5, "tw")
    assert await al.all("SM") == {
        ("song", 1): ["annyeong", "hello"],
        ("deck", 5): ["tw"],
    }
    assert await al.all("JYP") == {}
    assert await al.remove("SM", "song", 1, "HELLO")
    assert not await al.remove("SM", "song", 1, "hello")


async def test_display_names_replace_and_clear(database):
    names = database.display_names
    await names.set("SM", "deck", 5, "  M&D ")
    await names.set("SM", "deck", 5, "M & D")  # replaces
    await names.set("SM", "song", 1, "Hello")
    assert await names.all("SM") == {("deck", 5): "M & D", ("song", 1): "Hello"}
    assert await names.all("JYP") == {}
    assert await names.clear("SM", "deck", 5)
    assert not await names.clear("SM", "deck", 5)


def test_pool_size_comes_from_the_settings():
    from config import PostgresSettings

    assert PostgresSettings.from_env({}).pool_max == 2
    assert PostgresSettings.from_env({"POSTGRES_POOL_MAX": "4"}).pool_max == 4
    assert PostgresSettings.from_env({"POSTGRES_POOL_MAX": "0"}).pool_max == 1


async def test_the_pool_is_small(database):
    assert database.pool.get_max_size() == 2


async def test_every_statement_matches_the_schema(database):
    """asyncpg-typed checks a statement against Postgres only when it is
    prepared, and ``execute`` skips that. Prepare them all, so a statement
    whose declared types drift from the schema fails here."""
    import importlib
    import pkgutil

    import db as package

    prepared = 0
    async with database.pool.acquire() as conn:
        for info in pkgutil.iter_modules(package.__path__):
            module = importlib.import_module(f"db.{info.name}")
            for name, value in vars(module).items():
                if type(value).__name__ != "_SQLImpl" or name in {"_LOCK", "_UNLOCK"}:
                    continue  # the advisory-lock calls return void
                await value._prepare(conn)
                prepared += 1
    assert prepared >= 40


BIG = 1_335_315_390_732_963_952  # a real Discord id: far beyond a 32-bit integer


async def test_discord_sized_ids_work_everywhere(database):
    """The library treats every integer type as ``int``, so a 32-bit column
    or cast would only fail with ids this large."""
    await database.roles.add(BIG, [BIG, BIG - 1])
    await database.roles.change(BIG, add=[BIG - 2], remove=[BIG])
    assert await database.roles.get(BIG) == {BIG - 1, BIG - 2}

    wp = database.word_pings
    await wp.add(BIG, BIG, "cat")
    await wp.ignore(BIG, BIG, "user", BIG - 1)
    await wp.ignore(BIG, BIG, "channel", BIG - 2)
    assert await wp.unignore(BIG, BIG, "user", BIG - 1, "cat") == 1
    await wp.record_ping(BIG, BIG, "cat")
    again = type(wp)(database.pool)
    await again.load()
    assert again.get(BIG, BIG, "cat").count == 1
    assert again.get(BIG, BIG, "cat").channels == {BIG - 2}

    bp = database.bonus_pings
    assert await bp.subscribe(BIG, "SM", 1)
    assert await bp.preferences([BIG, BIG - 1]) == {
        BIG: PingPreferences(),
        BIG - 1: PingPreferences(),
    }
    await database.live_themes.set(BIG, "SM", 5)
    assert await database.live_themes.get(BIG, "SM") == 5


def test_tls_is_on_unless_told_otherwise_and_can_trust_a_given_ca(tmp_path):
    import ssl
    from pathlib import Path

    from config import PostgresSettings
    from db.database import tls_context

    assert tls_context(PostgresSettings("h", 1, "u", None, use_tls=False)) is False
    context = tls_context(PostgresSettings("h", 1, "u", None, use_tls=True))
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED
    env = {"POSTGRES_CA_FILE": "/run/secrets/ca.pem"}
    parsed = PostgresSettings.from_env(env)
    assert parsed.ca_file == Path("/run/secrets/ca.pem")
    assert PostgresSettings.from_env({}).ca_file is None
    assert parsed.use_tls
    assert not PostgresSettings.from_env({"POSTGRES_INSECURE": "1"}).use_tls
    missing = PostgresSettings("h", 1, "u", None, use_tls=True, ca_file=tmp_path / "x")
    with pytest.raises(FileNotFoundError):
        tls_context(missing)


async def test_song_stats_are_saved_by_song_and_versioned(database):
    stats = database.song_stats
    assert await stats.version("SM") == 0 and await stats.load("SM") == {}
    docs = {"1": {"duration": "3:21", "seq": {"Easy": {"count": 5}}}, "2": {"x": 1}}
    assert await stats.save("SM", docs) == 2
    assert await stats.version("SM") == 1
    assert await stats.load("SM") == docs
    assert await stats.save("SM", docs) == 0  # nothing changed: nothing written
    assert await stats.version("SM") == 1
    docs["2"] = {"x": 2}
    docs["nope"] = {"x": 3}  # not a song code: ignored
    assert await stats.save("SM", docs) == 1
    assert await stats.version("SM") == 2
    assert (await stats.load("SM"))["2"] == {"x": 2}
    assert await stats.load("BL") == {} and await stats.version("BL") == 0
    # Another instance (a new object) writes only what differs from what it loaded.
    other = type(stats)(database.pool)
    await other.load("SM")
    assert await other.save("SM", await other.load("SM")) == 0
