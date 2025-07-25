import asyncio
import logging
import random
from datetime import datetime, time
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

from statics.consts import ROLES, TIMEZONES

from .commons import PINATA_REWARDS, PINATA_TEST_CHANNEL

if TYPE_CHECKING:
    from dBot import dBot

    from .types import PinataDetails


class JoinAll(discord.ui.Button["PinataView"]):

    def __init__(self) -> None:
        super().__init__(label="Join All", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None
        await interaction.response.defer()
        self.view.joined[interaction.user] = [True] * self.view.length
        await self.view.message.edit(
            embed=generate_embed(self.view.rewards, self.view.joined)
        )


class LeaveAll(discord.ui.Button["PinataView"]):

    def __init__(self) -> None:
        super().__init__(label="Leave All", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None
        await interaction.response.defer()
        if interaction.user not in self.view.joined:
            return
        self.view.joined.pop(interaction.user)
        await self.view.message.edit(
            embed=generate_embed(self.view.rewards, self.view.joined)
        )


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


class PinataView(discord.ui.View):

    def __init__(
        self,
        rewards: list["PinataDetails"],
        message: discord.Message,
    ) -> None:
        self.rewards = rewards
        self.length = len(rewards)
        self.joined: dict[discord.User | discord.Member, list[bool]] = {}
        self.message = message
        super().__init__(timeout=30)
        self.add_item(JoinAll())
        for index, reward in enumerate(rewards):
            self.add_item(ToggleSpecific(label=reward["label"], index=index))
        self.add_item(LeaveAll())


class Pinata(commands.Cog):
    LOGGER = logging.getLogger(__name__.rpartition(".")[0])

    def __init__(self, bot: "dBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.pinata.start()

    async def cog_unload(self) -> None:
        self.pinata.cancel()

    @tasks.loop(time=[time(hour=h, minute=m) for h in range(24) for m in range(60)])
    async def pinata(self) -> None:
        current_date = datetime.now(tz=TIMEZONES["KST"]).strftime("%m%d")
        rewards = PINATA_REWARDS.get(current_date, [])
        if not rewards:
            return

        channel = self.bot.get_channel(
            PINATA_TEST_CHANNEL
        ) or await self.bot.fetch_channel(PINATA_TEST_CHANNEL)
        assert isinstance(channel, discord.TextChannel)

        real_rewards = [
            (
                {
                    "role": (
                        discord.utils.get(
                            channel.guild.roles,
                            id=reward["role"],
                        )
                        if isinstance(reward["role"], int)
                        else reward["role"]
                    ),
                    "of": reward["of"],
                }
            )
            for reward in rewards
        ]

        for reward in real_rewards:
            reward["mention"] = (
                f"{f"{reward["of"]} " if reward["of"] else ""}"
                f"{(reward["role"].mention
                    if isinstance(reward["role"], discord.Role)
                    else reward["role"])}"
            )
            reward["label"] = (
                f"{f"{reward["of"]} " if reward["of"] else ""}"
                f"{(reward["role"].name
                    if isinstance(reward["role"], discord.Role)
                    else reward["role"])}"
            )

        message = await channel.send(embed=generate_embed(real_rewards, {}))
        pinata_view = PinataView(
            rewards=real_rewards,  # type: ignore[arg-type]
            message=message,
        )
        await message.edit(view=pinata_view)
        await asyncio.sleep(30)
        for item in pinata_view.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        await message.edit(view=pinata_view)
        pinata_view.stop()

        random.seed(datetime.now().timestamp())
        for index, reward in enumerate(real_rewards):
            is_superstar = (
                isinstance(reward["role"], discord.Role)
                and reward["role"].id in ROLES[channel.guild.id]
            )
            is_member = (
                isinstance(reward["role"], discord.Role)
                and reward["role"].id not in ROLES[channel.guild.id]
            )
            if is_superstar:
                min_roll = 99.5
            else:
                min_roll = 99.0

            winner: discord.User | discord.Member | None = None
            yoink_list: list[discord.User | discord.Member] = []
            attendees_str = "Attendees:\n"

            for user, joined in pinata_view.joined.items():
                if joined[index]:
                    roll = random.randint(0, 10_000) / 100
                    if roll >= min_roll:
                        if winner is None:
                            winner = user
                            attendees_str += f"**`{roll}` {user.mention}**~~\n"
                        else:
                            yoink_list.append(user)
                            attendees_str += f"**`{roll}` {user.mention}**\n"
                    else:
                        attendees_str += f"`{roll}` {user.mention}\n"

            if winner is not None:
                attendees_str += "~~"

                final_desc = (
                    f"{winner.mention} broke the piñata "
                    f"and got **{reward["mention"]}**\n\n"
                )
                final_desc += attendees_str
            else:
                roll = rolls = 0
                while roll < min_roll:
                    roll = random.randint(0, 10_000) / 100
                    rolls += 1
                final_desc = (
                    f"**{rolls}** more rolls were needed "
                    f"to get a winner for **{reward["mention"]}**\n\n"
                )
                final_desc += attendees_str

            embed = discord.Embed(
                title="Piñata Drop",
                description=final_desc,
                color=(
                    reward["role"].color
                    if isinstance(reward["role"], discord.Role)
                    else None
                ),
            )
            embed.set_footer(text=f"Need to get {min_roll} or higher to win")
            await channel.send(embed=embed)

            if winner is not None:
                _message = (
                    f":tada:Congratulations {winner.mention}, "
                    f"you got **{reward["mention"]}**\n!"
                )

                if is_superstar:
                    assert isinstance(reward["role"], discord.Role)
                    if reward["role"].id not in self.bot.roles[str(winner.id)]:
                        self.bot.roles[str(winner.id)].append(reward["role"].id)

                    cog = self.bot.get_cog("DataSync")
                    cog.save_role_data()  # type: ignore[union-attr]

                    _message += "The role has been added to your inventory."
                elif is_member:
                    assert isinstance(winner, discord.Member)
                    assert isinstance(reward["role"], discord.Role)
                    await winner.add_roles(reward["role"])

                    _message += "The role has been added to your profile."

                await channel.send(
                    _message,
                    allowed_mentions=discord.AllowedMentions(
                        everyone=False, users=True, roles=False, replied_user=False
                    ),
                )

    @pinata.before_loop
    async def before_loop(self) -> None:
        await self.bot.wait_until_ready()


def generate_embed(
    rewards: list, attendees: dict[discord.User | discord.Member, list[bool]]
) -> discord.Embed:
    description = "Inside this piñata:\n**"
    color = None
    for reward in rewards:
        description += f"{reward["mention"]}\n"
        if isinstance(reward["role"], discord.Role) and color is None:
            color = reward["role"].color

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
        color=color,
    )
    embed.set_footer(text="Please refrain from joining if you already have the role(s)")
    return embed


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Pinata(bot))
