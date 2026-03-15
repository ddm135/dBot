import asyncio
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

from .common import GAME_OPTIONS, TEST_CHANNEL

if TYPE_CHECKING:
    from dBot import dBot


class Alice(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self) -> None:
        self.alice.start()

    async def cog_unload(self) -> None:
        self.alice.cancel()

    @tasks.loop(count=1)
    async def alice(self) -> None:
        channel = self.bot.get_channel(TEST_CHANNEL) or await self.bot.fetch_channel(
            TEST_CHANNEL
        )
        view = TriviaView(timeout=24 * 60 * 60)
        message = await channel.send("# Intermission", view=view)
        await asyncio.sleep(24 * 60 * 60)
        for item in view.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        await message.edit(view=view)
        view.stop()


class Q1(discord.ui.Modal, title="Question 1"):
    def __init__(self, view: "TriviaView"):
        self.view = view
        super().__init__()

    date = discord.ui.Label(
        text="When was the first SSRG shutdown?",
        component=discord.ui.TextInput(
            placeholder="YYYY-MM-DD",
            min_length=10,
            max_length=10,
            style=discord.TextStyle.short,
            required=True,
        ),
    )
    game = discord.ui.Label(
        text="Which game was it?",
        component=discord.ui.Select(
            options=GAME_OPTIONS,
            required=True,
            placeholder="Select a game",
        ),
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.view.submissions.setdefault(interaction.user.id, {})["Q1"] = {
            "date": self.date.component.value,
            "game": self.game.component.values[0],
        }


class TriviaView(discord.ui.View):
    submissions = {}

    @discord.ui.button(label="Question 1", style=discord.ButtonStyle.primary)
    async def question_1(
        self, interaction: discord.Interaction["dBot"], button: discord.ui.Button
    ):
        await interaction.response.send_modal(Q1(self))


# Q1: When was the first SSRG shutdown? (全民天团, 2017-04-27)

# Q2: Not counting JP versions, how many of the past games
# had major UI overhaul? (e.g., SSCL would not count)
# (2, BTS, WOOLLIM)

# Q3: Which game had the shortest service time? (THAILAND, 8 months)

# Q4: Which was the latest game to shutdown? (LAPONE, 2025-11-28)

# Q5: Not counting JP versions, how many of the past games had live themes?
# (7, WOOLLIM, GFRIEND, YG, FNC, THE BOYZ, CLASS:y, OH MY GIRL)

# Q6: Which year has the most shutdowns? (2024 with 6,
# YG JP, WOOLLIM, P NATION, BRANDNEW, LOOΠΔ, THAILAND)

# Q7-9: Which game used this as BGM?


async def setup(bot: "dBot"):
    await bot.add_cog(Alice(bot))
