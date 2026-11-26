"""A paginated message that only its requester can flip through."""

import logging
import math
from collections.abc import Callable, Sequence
from typing import Any

import discord

logger = logging.getLogger(__name__)

NOT_REQUESTER = "You are not the original requester."


def page_count(total: int, per_page: int) -> int:
    """How many pages ``total`` items make; at least one."""
    return max(1, math.ceil(total / per_page))


def slice_page[T](items: Sequence[T], page: int, per_page: int) -> Sequence[T]:
    """The items of a 1-based ``page``."""
    end = page * per_page
    return items[end - per_page : end]


class Paginator(discord.ui.View):
    """Previous/next buttons around an embed that depends on the page.

    ``render(page, pages)`` builds the embed of a 1-based page. Pages wrap
    around, as they did in v0.
    """

    def __init__(
        self,
        owner: discord.abc.User,
        render: Callable[[int, int], discord.Embed],
        pages: int,
        *,
        page: int = 1,
        timeout: float | None = 180.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.owner = owner
        self.render = render
        self.pages = max(1, pages)
        self.page = min(max(1, page), self.pages)
        self.message: discord.Message | discord.WebhookMessage | None = None

    def embed(self) -> discord.Embed:
        return self.render(self.page, self.pages)

    async def start(self, itr: discord.Interaction[Any], **kwargs: Any) -> None:
        """Send the first page as the interaction's followup."""
        if self.pages > 1:
            self.message = await itr.followup.send(
                embed=self.embed(), view=self, wait=True, **kwargs
            )
        else:  # nothing to flip through
            await itr.followup.send(embed=self.embed(), **kwargs)
            self.stop()

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                logger.debug("Could not disable the pager.", exc_info=True)

    async def interaction_check(self, interaction: discord.Interaction[Any]) -> bool:
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message(NOT_REQUESTER, ephemeral=True)
            return False
        return True

    async def show(self, interaction: discord.Interaction[Any]) -> None:
        await interaction.response.edit_message(embed=self.embed(), view=self)

    def step(self, delta: int) -> None:
        self.page = (self.page - 1 + delta) % self.pages + 1

    @discord.ui.button(label="Previous Page", style=discord.ButtonStyle.primary)
    async def previous_page(
        self, interaction: discord.Interaction[Any], _: discord.ui.Button[Any]
    ) -> None:
        self.step(-1)
        await self.show(interaction)

    @discord.ui.button(label="Next Page", style=discord.ButtonStyle.success)
    async def next_page(
        self, interaction: discord.Interaction[Any], _: discord.ui.Button[Any]
    ) -> None:
        self.step(1)
        await self.show(interaction)
