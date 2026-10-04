"""Finding a channel by id."""

import logging

import discord

logger = logging.getLogger(__name__)


async def find_channel[T](
    bot: discord.Client, channel_id: int, kind: type[T]
) -> T | None:
    """The channel, from the cache or else from Discord; None if it is not a ``kind``.

    A channel the bot cannot see (deleted, no access) is also None.
    """
    try:
        channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
    except discord.HTTPException:
        logger.warning("Channel %d is not reachable.", channel_id)
        return None
    if not isinstance(channel, kind):
        logger.warning("Channel %d is not a %s.", channel_id, kind.__name__)
        return None
    return channel
