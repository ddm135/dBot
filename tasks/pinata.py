import logging
import random
from datetime import date, time
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

from statics.consts import PINATA, PINATA_TEST_CHANNEL, ROLES

if TYPE_CHECKING:
    from dBot import dBot


class ToggleSpecific(discord.ui.Button["PinataView"]):

    def __init__(self, label: str, index: int) -> None:
        self.index = index
        super().__init__(label=label, style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None
        await interaction.response.defer()
        joined = self.view.joined.setdefault(
            interaction.user, [False] * self.view.length
        )
        joined[self.index] = not joined[self.index]
        if not any(joined):
            self.view.joined.pop(interaction.user)
        await self.view.message.edit(
            embed=generate_embed(self.view.rewards, self.view.joined)
        )
        await self.view.message.edit(view=self.view)


class PinataView(discord.ui.View):

    def __init__(
        self,
        rewards: list[dict[str, discord.Role | str]],
        message: discord.Message,
    ) -> None:
        self.rewards = rewards
        self.length = len(rewards)
        self.joined: dict[discord.User | discord.Member, list[bool]] = {}
        self.message = message
        super().__init__(timeout=30)
        for index, reward in enumerate(rewards):
            self.add_item(ToggleSpecific(label=reward["label"], index=index))

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        await self.message.edit(view=self)
        await super().on_timeout()

    @discord.ui.button(label="Join", style=discord.ButtonStyle.success)
    async def join_pinata(
        self, itr: discord.Interaction["dBot"], button: discord.ui.Button
    ) -> None:
        await itr.response.defer()
        self.joined[itr.user] = [True] * self.length
        await self.message.edit(embed=generate_embed(self.rewards, self.joined))

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.danger)
    async def leave_pinata(
        self, itr: discord.Interaction["dBot"], button: discord.ui.Button
    ) -> None:
        await itr.response.defer()
        if itr.user not in self.joined:
            return
        self.joined.pop(itr.user)
        await self.message.edit(embed=generate_embed(self.rewards, self.joined))


class Pinata(commands.Cog):
    LOGGER = logging.getLogger(__name__)

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.pinata.start()
        await super().cog_load()

    async def cog_unload(self) -> None:
        self.pinata.cancel()
        await super().cog_unload()

    @tasks.loop(time=[time(hour=h, minute=m) for h in range(24) for m in range(60)])
    async def pinata(self) -> None:
        current_date = date.today().strftime("%m%d")
        rewards = PINATA.get(current_date, [])
        if not rewards:
            return
        channel = self.bot.get_channel(PINATA_TEST_CHANNEL)
        real_rewards = [
            (
                {
                    "role": (
                        discord.utils.get(
                            channel.guild.roles,  # type: ignore[union-attr]
                            id=reward["role"],
                        )
                        if isinstance(reward["role"], int)
                        else reward["role"]
                    ),
                    "from": reward["from"],
                }
            )
            for reward in rewards
        ]
        for reward in real_rewards:
            reward["label"] = (
                f"{f"{reward["from"]} " if reward["from"] else ""}"
                f"{reward["role"].mention if isinstance(reward["role"], discord.Role) else reward["role"]}"
            )
        message = await channel.send(  # type: ignore[union-attr]
            embed=generate_embed(real_rewards, {})
        )
        pinata_view = PinataView(
            rewards=real_rewards,  # type: ignore[arg-type]
            message=message,
        )
        await message.edit(view=pinata_view)
        await pinata_view.wait()

        for index, reward in enumerate(real_rewards):
            is_superstar = (
                isinstance(reward["role"], discord.Role)
                and reward["role"].id in ROLES[channel.guild.id]
            )
            if is_superstar:
                min_roll = 50
            else:
                min_roll = 50
            winner: discord.User | discord.Member | None = None
            yoink_list: list[discord.User | discord.Member] = []
            attendees_str = "Attendees:\n"
            for user, joined in pinata_view.joined.items():
                if joined[index]:
                    roll = random.randint(0, 10_000) / 100
                    if roll > min_roll:
                        if winner is None:
                            winner = user
                            attendees_str += f"**`{roll}` {user.name}**~~\n"
                        else:
                            yoink_list.append(user)
                            attendees_str += f"**`{roll}` {user.name}**\n"
                    else:
                        attendees_str += f"`{roll}` {user.name}\n"
            if winner is not None:
                attendees_str += "~~"
            await channel.send(attendees_str)  # type: ignore[union-attr]

    @pinata.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()


def generate_embed(
    rewards: list, attendees: dict[discord.User | discord.Member, list[bool]]
) -> discord.Embed:
    description = "Inside this piñata:\n**"
    for reward in rewards:
        description += f"{reward["label"]}\n"
    description += "**\nLining Up:\n"
    if not attendees:
        description += "None"
    else:
        for index, (attendee, joined) in enumerate(attendees.items(), start=1):
            for j in joined:
                if j:
                    description += "◼"
                else:
                    description += "◻"
            description += f" {index}. {attendee.mention}\n"

    embed = discord.Embed(
        title="Piñata Drop",
        description=description,
    )
    return embed


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Pinata(bot))
