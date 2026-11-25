import re

from db.word_pings import word_pattern
from games.media.drive import query
from templates import Raw, render
from ui.text import md


def test_md_escapes_interpolations_only():
    name = "a_b*c"
    assert md(t"**{name}** - {1234:,}") == "**a\\_b\\*c** - 1,234"


def test_raw_is_inserted_as_is():
    assert md(t"- {Raw('**x**')}: {'y_'}") == "- **x**: y\\_"


def test_conversion_and_spec_apply_before_quoting():
    assert render(t"{'a_':>4}|{'b_'!r}", str.upper) == "  A_|'B_'"


def test_drive_query_quotes_the_folder():
    assert query(t"'{chr(39) + 'x'}' in parents") == "'\\'x' in parents"


def test_word_pattern_escapes_the_word_but_not_the_boundaries():
    pattern = word_pattern("a.b")
    assert pattern.search("say a.b now")
    assert not pattern.search("say axb now")
    assert isinstance(pattern, re.Pattern)
