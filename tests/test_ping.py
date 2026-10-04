from cogs.ping import recipients
from db.word_pings import Subscription


def test_recipients_skip_the_author_ignores_and_repeats():
    matches = [
        (
            "cat",
            {
                1: Subscription(),
                2: Subscription(users={9}),
                3: Subscription(channels={7}),
                9: Subscription(),
            },
        ),
        ("dog", {1: Subscription(), 4: Subscription()}),
    ]
    # Author 9 in channel 7: 9 is skipped (author), 2 ignores user 9, 3 ignores channel 7,
    # 1 is pinged once (cat), 4 for dog.
    assert recipients(matches, 9, 7) == [("cat", 1), ("dog", 4)]
    assert recipients([], 9, 7) == []
