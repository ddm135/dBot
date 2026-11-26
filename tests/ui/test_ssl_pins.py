from types import SimpleNamespace

from ui.ssl_pins import SslPinner


class Pin:
    def __init__(self, id, author, embed_author):
        self.id = id
        self.author = SimpleNamespace(id=author)
        self.embeds = (
            [SimpleNamespace(author=SimpleNamespace(name=embed_author))]
            if embed_author is not None
            else []
        )
        self.unpinned = False

    async def unpin(self):
        self.unpinned = True


class Channel:
    def __init__(self, pins):
        self._pins = pins

    async def pins(self):
        for pin in self._pins:
            yield pin


async def test_only_todays_post_stays_pinned():
    me = 99
    pins = [
        Pin(1, me, "SUPERSTAR SM - SSL #1"),  # an earlier day: unpinned
        Pin(2, me, "SUPERSTAR SM - SSL #5"),  # another weekday: unpinned too
        Pin(3, me, "SUPERSTAR SM - SSL #3"),  # the new post
        Pin(4, me, "SUPERSTAR SS - SSL #2"),  # another game: left alone
        Pin(5, 7, "SUPERSTAR SM - SSL #4"),  # not the bot's: left alone
        Pin(6, me, None),  # no embed: left alone
    ]
    pinner = SslPinner(SimpleNamespace(user=SimpleNamespace(id=me)))
    await pinner._unpin_old(Channel(pins), 3, "SUPERSTAR SM - SSL #")
    assert [p.unpinned for p in pins] == [True, True, False, False, False, False]


async def test_run_all_pins_each_game_and_survives_one_failing():
    import asyncio
    from types import SimpleNamespace

    from tasks.pin_ssl import PinSSL

    games = [
        SimpleNamespace(key="A", has_pins=True),
        SimpleNamespace(key="B", has_pins=True),
    ]
    bot = SimpleNamespace(games=[SimpleNamespace(game=g) for g in games])
    cog = PinSSL(bot)
    seen = []

    async def pin_game(game):
        seen.append(game.key)
        if game.key == "A":
            raise RuntimeError("boom")

    cog.pin_game = pin_game
    await asyncio.wait_for(cog.run_all(), 1)
    await asyncio.wait_for(cog.run_all(), 1)  # the startup run, then the hourly one
    assert seen == ["A", "B", "A", "B"]
