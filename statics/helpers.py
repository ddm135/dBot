# pyright: reportMissingModuleSource=false

import asyncio

import discord


async def pin_new_ssl(
    embed: discord.Embed,
    pin_channel: discord.TextChannel,
) -> int:
    msg = await pin_channel.send(embed=embed)
    await asyncio.sleep(1)
    await msg.pin()
    return msg.id


async def unpin_old_ssl(
    embed_title: str | None, pin_channel: discord.TextChannel, new_pin: int
) -> None:
    if embed_title is None:
        return

    pins = await pin_channel.pins()
    for pin in pins:
        if pin.id == new_pin:
            continue

        embeds = pin.embeds
        if embeds and embeds[0].title and embed_title in embeds[0].title:
            await pin.unpin()
            break


def get_column_letter(index: int) -> str:
    return chr((index) % 26 + ord("A"))
