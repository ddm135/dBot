"""The box embed, its buttons, and the result of a draw."""

from collections.abc import Callable, Hashable
from typing import Protocol

import discord

from pinata.lottery import Draw, Entries

TITLE = "Guitar Collecting"
IMAGE = "attachment://guitar.png"
WINDOW_SECONDS = 300
FILLED, EMPTY = "◼", "◻"


class Person(Hashable, Protocol):
    @property
    def mention(self) -> str: ...


def box_embed[T: Person](
    mentions: list[str], colour: discord.Colour | None, entries: Entries[T]
) -> discord.Embed:
    """What is inside the box and who is lined up."""
    text = (
        "Inside this box:\n**"
        + "".join(f"{m}\n" for m in mentions)
        + "**\nLining Up:\n"
    )
    if not entries:
        text += "None"
    for number, (who, flags) in enumerate(entries, start=1):
        marks = "".join(FILLED if f else EMPTY for f in flags)
        text += f"{marks} {number}. {who.mention}\n"
    embed = discord.Embed(title=TITLE, description=text, colour=colour)
    embed.set_footer(
        text="Please refrain from joining if you already have the role(s)",
        icon_url=IMAGE,
    )
    return embed


def result_embed[T: Person](
    draw: Draw[T],
    mention: str,
    colour: discord.Colour | None,
    *,
    nobody_joined: bool,
) -> discord.Embed:
    """The rolls of one prize. Everyone after the winner is struck through."""
    lines = "Attendees:\n"
    won = False
    for who, value in draw.rolls:
        reached = value >= draw.minimum
        if reached and draw.winner is who and not won:
            lines += f"**`{value}` {who.mention}**~~\n"
            won = True
        elif reached:
            lines += f"**`{value}` {who.mention}**\n"
        else:
            lines += f"`{value}` {who.mention}\n"
    if draw.winner is not None:
        text = (
            f"{draw.winner.mention} opened the box and got **{mention}**\n\n{lines}~~"
        )
    else:
        text = (
            f"**{draw.rolls_needed}** more rolls were needed "
            f"to get a winner for **{mention}**\n\n{lines}"
        )
        if nobody_joined:
            text += "None"
    embed = discord.Embed(title=TITLE, description=text, colour=colour)
    embed.set_footer(
        text=f"Need to get {draw.minimum} or higher to win", icon_url=IMAGE
    )
    return embed


class BoxView[T: Person](discord.ui.View):
    """Join all, one toggle per prize, and leave all."""

    def __init__(
        self,
        labels: list[str],
        entries: Entries[T],
        render: Callable[[], discord.Embed],
        *,
        timeout: float = WINDOW_SECONDS,
    ) -> None:
        super().__init__(timeout=timeout)
        self.entries = entries
        self._render = render
        self.add_item(self._button("Join All", discord.ButtonStyle.success, None))
        for index, label in enumerate(labels):
            self.add_item(self._button(label, discord.ButtonStyle.primary, index))
        self.add_item(self._button("Leave All", discord.ButtonStyle.danger, -1))

    def _button(
        self, label: str, style: discord.ButtonStyle, prize: int | None
    ) -> discord.ui.Button[BoxView[T]]:
        button: discord.ui.Button[BoxView[T]] = discord.ui.Button(
            label=label, style=style
        )

        async def callback(interaction: discord.Interaction) -> None:
            who: T = interaction.user  # type: ignore[assignment]
            if prize is None:
                self.entries.join_all(who)
            elif prize < 0:
                self.entries.leave_all(who)
            else:
                self.entries.toggle(who, prize)
            await interaction.response.edit_message(embed=self._render())

        button.callback = callback  # type: ignore[method-assign]
        return button

    def close(self) -> None:
        """No more joining."""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        self.stop()
