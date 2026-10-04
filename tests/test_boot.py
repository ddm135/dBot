import pytest

from bot import dBot
from config import Settings
from extensions import EXTENSIONS
from games.accounts import Accounts
from search import Searcher


@pytest.fixture
async def bot(database, tmp_path):
    settings = Settings.from_env(
        {"DISCORD_TOKEN": "x", "AES_KEY": "k" * 16, "VALKEY_HOST": "localhost"}
    )
    bot = dBot(settings)
    bot.db = database
    bot.accounts = Accounts(bot.games.server, database.credentials)
    bot.search = Searcher(bot.indexes, database.aliases)
    yield bot
    await bot.web.aclose()


async def test_every_extension_loads_and_unloads(bot):
    for name in EXTENSIONS:
        await bot.load_extension(name)
    commands = {c.name: c for c in bot.tree.get_commands()}
    assert {"info", "bonus", "ping", "role", "ssl"} <= set(commands)

    bonus = commands["bonus"]
    assert {c.name for c in bonus.commands} == {"list", "top", "live_theme", "ping"}
    assert {c.name for c in bonus.get_command("ping").commands} == {
        "add",
        "remove",
        "list",
        "time",
    }
    assert {c.name for c in commands["ping"].commands} == {
        "add",
        "remove",
        "list",
        "ignore",
        "unignore",
    }
    assert {c.name for c in commands["ssl"].commands} == {"pin_by_name", "pin_by_id"}
    assert {c.name for c in commands["role"].commands} == {
        "add",
        "remove",
        "set",
        "inventory",
    }

    prefix = {c.name for c in bot.commands}
    assert {
        "pull",
        "sync",
        "load",
        "reload",
        "resync",
        "alias",
        "mots7",
        "bonusbot",
    } <= prefix

    info = commands["info"]
    assert [p.name for p in info.parameters] == ["game", "artist", "song"]
    game_choices = {c.value for c in info.parameters[0].choices}
    assert {"BL", "SM"} <= game_choices  # BL has its songs in its tables too

    bonus_games = {c.value for c in bonus.get_command("list").parameters[0].choices}
    assert (
        bonus_games == {"SM", "JYP", "ATZ", "SC", "SMTOWN", "PH", "SS"}
        or "SM" in bonus_games
    )

    for name in EXTENSIONS:
        await bot.unload_extension(name)
