import asyncio
import logging
from types import SimpleNamespace

from tasks.game_sync import BasicSync
from tasks.hourly import HourlyTask


class Bot(SimpleNamespace):
    def __init__(self, *keys: str, preferred: bool = True) -> None:
        async def ready() -> None:
            return None

        class Games(list):  # a list of games that can be waited for
            wait_until_ready = staticmethod(ready)

        super().__init__(
            games=Games(SimpleNamespace(game=SimpleNamespace(key=k)) for k in keys),
            settings=SimpleNamespace(preferred=preferred),
        )


class Task(HourlyTask):
    failure = "Task failed."

    def __init__(self, bot, *, fail: str | None = None) -> None:
        super().__init__(bot)
        self.seen: list[str] = []
        self.finished = 0
        self.fail = fail

    async def run_game(self, data) -> None:
        if data.game.key == self.fail:
            raise RuntimeError("boom")
        self.seen.append(data.game.key)

    async def finish(self) -> None:
        self.finished += 1


async def test_every_game_is_done_and_a_failure_is_logged_and_skipped(caplog):
    task = Task(Bot("A", "B", "C"), fail="B")
    with caplog.at_level(logging.ERROR):
        assert await task.run_all() is True
    assert task.seen == ["A", "C"] and task.finished == 1
    assert "B: Task failed." in caplog.text


async def test_only_the_preferred_instance_runs_what_is_preferred_only():
    task = Task(Bot("A", preferred=False))
    task.only_preferred = True
    assert await task.run_all() is False and task.seen == [] and task.finished == 0
    task.bot.settings.preferred = True
    assert await task.run_all() is True and task.seen == ["A"]


async def test_a_run_is_skipped_while_one_is_going_unless_it_waits():
    task = Task(Bot("A"))
    async with task._running:
        assert await task.run_all() is False
        task.skip_when_running = False
        waiting = asyncio.create_task(task.run_all())
        await asyncio.sleep(0.01)
        assert not waiting.done()  # it waits for the one before
    assert await waiting is True and task.seen == ["A"]


async def test_games_can_be_chosen_by_the_task():
    class Some(Task):
        def games(self):
            return (d for d in self.bot.games if d.game.key != "B")

    task = Some(Bot("A", "B"))
    await task.run_all()
    assert task.seen == ["A"]


async def test_the_start_up_run_is_optional():
    task = Task(Bot("A"))
    await task.cog_load()
    assert task._startup is not None
    await task._startup
    assert task.seen == ["A"]
    await task.cog_unload()

    sync = BasicSync(Bot("A"))
    await sync.cog_load()
    assert sync._startup is None  # the first sync is made by the data service
    await sync.cog_unload()
