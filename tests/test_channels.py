from types import SimpleNamespace

import discord

from channels import find_channel


class Text(discord.TextChannel):
    def __init__(self):
        pass


def bot(cached=None, fetched=None, error=None):
    calls = []

    async def fetch_channel(channel_id):
        calls.append(channel_id)
        if error:
            raise error
        return fetched

    return (
        SimpleNamespace(
            get_channel=lambda channel_id: cached, fetch_channel=fetch_channel
        ),
        calls,
    )


async def test_a_cached_channel_is_not_fetched():
    channel = Text()
    client, calls = bot(cached=channel)
    assert await find_channel(client, 1, discord.TextChannel) is channel
    assert calls == []


async def test_an_uncached_channel_is_fetched():
    channel = Text()
    client, calls = bot(fetched=channel)
    assert await find_channel(client, 7, discord.TextChannel) is channel
    assert calls == [7]


async def test_missing_or_wrong_channels_are_none():
    gone = discord.NotFound(SimpleNamespace(status=404, reason="x"), "gone")
    client, _ = bot(error=gone)
    assert await find_channel(client, 1, discord.TextChannel) is None
    client, _ = bot(cached=Text())
    assert await find_channel(client, 1, discord.VoiceChannel) is None
