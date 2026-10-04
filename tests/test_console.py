from typing import ClassVar

import pytest

from lease.console import MAX_OUTPUT, LookupFailed, lookup, render


class Thing:
    name = "n"
    items: ClassVar = [1, 2, {"a": 3}]
    mapping: ClassVar = {"key": [10, 20]}

    @property
    def broken(self):
        raise RuntimeError("boom")


def test_paths_follow_attributes_keys_and_indices():
    thing = Thing()
    assert lookup(thing, "name") == "n"
    assert lookup(thing, "items[1]") == 2
    assert lookup(thing, "mapping['key'][1]") == 20


@pytest.mark.parametrize(
    "path", ["", "???", "nope", "items[9]", "mapping['x']", "name[0]", "broken"]
)
def test_a_bad_path_is_reported_not_raised(path):
    with pytest.raises(LookupFailed):
        lookup(Thing(), path)


def test_render_survives_a_failing_repr_and_caps_long_output():
    class Bad:
        def __repr__(self):
            raise ValueError("no")

    assert render(Bad()).startswith("Could not print the value")
    assert "more characters" in render("x" * (MAX_OUTPUT * 2))


def test_a_missing_name_suggests_close_ones_and_bot_is_the_root():
    thing = Thing()
    with pytest.raises(LookupFailed, match="Did you mean: name"):
        lookup(thing, "nam")
    assert lookup(thing, "bot.name") == "n" and lookup(thing, "bot") is thing
    from lease.console import names

    assert "items" in names(thing) and not any(n.startswith("_") for n in names(thing))
