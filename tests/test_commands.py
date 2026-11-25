from datetime import UTC, datetime
from types import SimpleNamespace

from discord import app_commands

from cogs.bonus import Bonus
from cogs.info import Info
from games.charts.song_stats import SongStatsStore
from games.index import Indexes
from games.media.images import ImageService
from games.registry import GAMES
from search import Searcher

from .data import MemoryStats, Tables
from .test_index_search import FakeService

SM = GAMES["SM"]


class Sent:
    def __init__(self):
        self.calls = []

    async def send(self, content=None, **kwargs):
        self.calls.append((content, kwargs))
        return SimpleNamespace(edit=lambda **k: None)


class Itr:
    def __init__(self, user_id=1):
        self.followup = Sent()
        self.user = SimpleNamespace(id=user_id, color=0)
        self.namespace = SimpleNamespace()
        self.responded = []
        self.response = SimpleNamespace(defer=self._defer, send_message=self._send)

    async def _defer(self, **kwargs):
        pass

    async def _send(self, content=None, **kwargs):
        self.responded.append((content, kwargs))

    @property
    def last(self):
        return self.followup.calls[-1]


def world(tmp_path, database, now=datetime(2025, 9, 20, 12, tzinfo=UTC)):
    t = Tables()
    t.group(1, "TWICE")
    t.group(2, "BTS")
    t.artist(10, "Nayeon", 1, birthday=(1995, 9, 22))
    t.artist(20, "Jungkook", 2, birthday=(1997, 9, 1))
    t.song(100, "Cheer Up", 1, artists=[10], release=(2016, 4, 25))
    t.song(101, "Fancy", 1, artists=[10], release=(2019, 4, 22))
    t.song(200, "Dynamite", 2, artists=[20])
    service = FakeService(t.as_tables())
    service.data.icon_url = "http://icon"
    indexes = Indexes(service, clock=lambda g: now.replace(tzinfo=g.timezone))
    stats = MemoryStats(
        {
            "SM": {
                "100": {
                    "duration": "3:10",
                    "seq": {
                        "Easy": {"count": 100},
                        "Hard": {"count": 300},
                        "Normal": {"count": 200},
                    },
                },
                "101": {
                    "duration": "2:30",
                    "seq": {"4": {"count": 50}, "9": {"count": 150}},
                },
            }
        }
    )
    bot = SimpleNamespace(
        db=database,
        indexes=indexes,
        stats=SongStatsStore(stats),
        games=service,
        search=Searcher(indexes, database.aliases),
        images=ImageService(None, service, indexes),  # type: ignore[arg-type]
    )
    return bot


def choice(game="SM"):
    return app_commands.Choice(name=GAMES[game].name, value=game)


async def test_info_lists_all_songs_shortest_first(tmp_path, database):
    bot = world(tmp_path, database)
    itr = Itr()
    await Info.info.callback(Info(bot), itr, choice())
    _, kwargs = itr.last
    lines = kwargs["embed"].description.splitlines()
    assert [line.split(")")[0] for line in lines] == ["(2:30", "(3:10", "(Unknown"]
    assert "TWICE - **Fancy**" in lines[0]


async def test_info_for_one_artist_and_one_song(tmp_path, database):
    bot = world(tmp_path, database)
    itr = Itr()
    await Info.info.callback(Info(bot), itr, choice(), artist="1")
    assert itr.last[1]["embed"].title == "TWICE"
    assert "Dynamite" not in itr.last[1]["embed"].description

    itr = Itr()
    await Info.info.callback(Info(bot), itr, choice(), artist="1", song="100")
    embed = itr.last[1]["embed"]
    fields = {f.name: f.value for f in embed.fields}
    assert fields["Duration"] == "3:10"
    assert fields["Note Count"] == "100 / 200 / 300"
    assert "Difficulty Levels" not in fields  # Easy / Hard / Normal is the default

    itr = Itr()
    await Info.info.callback(Info(bot), itr, choice(), artist="1", song="101")
    fields = {f.name: f.value for f in itr.last[1]["embed"].fields}
    assert fields["Difficulty Levels"] == "4 / 9"


async def test_info_shows_a_song_chosen_without_its_artist(tmp_path, database):
    bot = world(tmp_path, database)
    both, alone = Itr(), Itr()
    await Info.info.callback(Info(bot), both, choice(), artist="1", song="101")
    await Info.info.callback(Info(bot), alone, choice(), song="101")
    assert alone.last[1]["embed"].to_dict() == both.last[1]["embed"].to_dict()


async def test_info_reports_bad_input(tmp_path, database):
    bot = world(tmp_path, database)
    for kwargs, text in [
        ({"artist": "99"}, "Artist not found."),
        ({"song": "9999"}, "Song not found."),
        ({"artist": "2", "song": "100"}, "Song not found."),
    ]:
        itr = Itr()
        await Info.info.callback(Info(bot), itr, choice(), **kwargs)
        assert itr.last[0] == text
    bot.indexes._service.set(None)
    itr = Itr()
    await Info.info.callback(Info(bot), itr, choice())
    assert itr.last[0] == "There is no data for this game yet."


async def test_bonus_list_shows_overlapping_bonuses(tmp_path, database):
    bot = world(tmp_path, database)
    itr = Itr()
    await Bonus.list_.callback(Bonus(bot), itr, choice(), None, None, None)
    embed = itr.last[1]["embed"]
    names = [f.name for f in embed.fields]
    assert any("Nayeon" in n for n in names)
    assert any(":white_check_mark:" in n for n in names)  # Sep 20 is inside 9/19-25

    itr = Itr()
    await Bonus.list_.callback(Bonus(bot), itr, choice(), "2", None, None)
    assert "Nayeon" not in str(itr.last[1]["embed"].fields)
    assert "Jungkook" in str(itr.last[1]["embed"].fields)

    itr = Itr()
    await Bonus.list_.callback(Bonus(bot), itr, choice(), None, None, 999)
    assert "at most" in itr.last[0]


async def test_bonus_top_builds_the_view_with_its_buttons(tmp_path, database):
    bot = world(tmp_path, database)
    itr = Itr()
    await Bonus.top.callback(Bonus(bot), itr, choice(), None)
    view = itr.last[1]["view"]
    first = itr.last[1]["embed"]
    # As in v0 the embed has the game's name and no title; the decks are fields.
    assert first.title is None and first.author.name == f"{SM.name} - Top Bonuses"
    assert first.fields[0].name == "TWICE"
    assert view.highest_button.disabled and not view.all_button.disabled
    view.showing_max = True
    assert view.embed().title == "Max Score of This Week"
    view.showing_max = False
    view.mode = "all"
    assert view.embed().footer.text.startswith("Page 1/")


async def test_live_theme_and_ping_settings(tmp_path, database):
    bot = world(tmp_path, database)
    cog = Bonus(bot)
    itr = Itr(user_id=5)
    await Bonus.live_theme.callback(cog, itr, choice(), 0)
    assert await database.live_themes.get(5, "SM") == 0
    itr = Itr(user_id=5)
    await Bonus.ping_add.callback(cog, itr, choice(), "1")
    assert await database.bonus_pings.decks_of(5, "SM") == [1]
    itr = Itr(user_id=5)
    await Bonus.ping_time.callback(cog, itr, 3, None)
    assert "3 hours before" in itr.last[0]
    itr = Itr(user_id=5)
    await Bonus.ping_list.callback(cog, itr)
    content, kwargs = itr.last
    assert "Start pings: 3 hours before" in content
    (embed,) = kwargs["embeds"]  # one embed per game, like v0
    assert embed.author.name == SM.name and embed.description == "- TWICE"
    itr = Itr(user_id=5)
    await Bonus.ping_remove.callback(cog, itr, choice(), "1")
    assert itr.last[0] == "Removed."


async def test_highest_only_lists_every_deck_with_only_its_best_entries(
    tmp_path, database
):
    from cogs.bonus import collect, highest_only
    from ui.bonus import week_range

    bot = world(tmp_path, database)
    index = bot.indexes.get("SM")
    calendar = bot.indexes.current_calendar("SM")
    today = bot.indexes.today(SM)
    items = collect(index, calendar, week_range(today), None)
    best = highest_only(index, items, 0)
    # Every deck with a bonus is there, best score first, and each keeps only
    # the entries that tie for its best total.
    assert [i.deck.code for i in best] == [
        i.deck.code for i in sorted(items, key=lambda i: -i.best(index, 0))
    ]
    for item in best:
        totals = {e.total for e in item.entries}
        assert len(totals) == 1


async def test_info_attaches_decoded_images(tmp_path, database):
    from games.media.images import Picture

    class Images:
        async def emblem(self, game, deck):
            return Picture(data=b"emblem", filename="e.png")

        async def album(self, game, song):
            return Picture(data=b"album", filename="a.png")

    bot = world(tmp_path, database)
    bot.images = Images()
    itr = Itr()
    await Info.info.callback(Info(bot), itr, choice(), artist="1", song="100")
    _, kwargs = itr.last
    embed = kwargs["embed"]
    assert embed.thumbnail.url == "attachment://album_a.png"
    assert embed.author.icon_url == "attachment://emblem_e.png"
    assert sorted(f.filename for f in kwargs["files"]) == [
        "album_a.png",
        "emblem_e.png",
    ]

    itr = Itr()
    await Info.info.callback(Info(bot), itr, choice(), artist="1")
    _, kwargs = itr.last
    assert kwargs["embed"].author.icon_url == "attachment://emblem_e.png"
    assert [f.filename for f in kwargs["files"]] == ["emblem_e.png"]
