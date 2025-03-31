import json
import logging
import random
from datetime import date, datetime, time
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

from statics.consts import PINATA, PINATA_TEST_CHANNEL, ROLE_DATA, ROLES
from statics.types import PinataDetails

if TYPE_CHECKING:
    from dBot import dBot


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
        rewards: list[PinataDetails],
        message: discord.Message,
    ) -> None:
        self.rewards = rewards
        self.length = len(rewards)
        self.joined: dict[discord.User | discord.Member, list[bool]] = {}
        self.message = message
        super().__init__(timeout=random.randint(200, 400))
        self.add_item(JoinAll())
        for index, reward in enumerate(rewards):
            self.add_item(ToggleSpecific(label=reward["label"], index=index))
        self.add_item(LeaveAll())

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        await self.message.edit(view=self)
        await super().on_timeout()


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

    @tasks.loop(
        time=[
            time(hour=h, minute=m)
            for (h, m) in (
                (0, 0),
                (1, 2),
                (2, 14),
                (3, 38),
                (4, 20),
                (5, 54),
                (6, 23),
                (7, 11),
                (8, 24),
                (9, 37),
                (10, 46),
                (11, 0),
                (12, 40),
                (13, 49),
                (14, 16),
                (15, 4),
                (16, 26),
                (17, 51),
                (18, 0),
                (19, 16),
                (20, 1),
                (21, 32),
                (22, 30),
                (23, 43),
            )
        ]
    )
    async def pinata(self) -> None:
        current_date = date.today().strftime("%m%d")
        rewards = PINATA.get(current_date, [])
        if not rewards:
            return

        channel = self.bot.get_channel(402632825834307584)
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
                    "from": reward["from"],
                }
            )
            for reward in rewards
        ]

        for reward in real_rewards:
            reward["mention"] = (
                f"{f"{reward["from"]} " if reward["from"] else ""}"
                f"{(reward["role"].mention
                    if isinstance(reward["role"], discord.Role)
                    else reward["role"])}"
            )
            reward["label"] = (
                f"{f"{reward["from"]} " if reward["from"] else ""}"
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
        await pinata_view.wait()

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
                min_roll = 99.99

            winner: discord.User | discord.Member | None = None
            yoink_list: list[discord.User | discord.Member] = []
            attendees_str = "Attendees:\n"

            for user, joined in pinata_view.joined.items():
                if joined[index]:
                    roll = random.randint(0, 10_000) / 100
                    if roll > min_roll:
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
                    f"{winner.mention} broke the guitar "
                    f"and got **{reward["mention"]}**\n\n"
                )
                final_desc += attendees_str
            else:
                rolls = 1
                while True:
                    roll = random.randint(0, 10_000) / 100
                    if roll > min_roll:
                        break
                    rolls += 1
                final_desc = (
                    f"**{rolls}** more guitars were needed "
                    f"to get a winner for **{reward["mention"]}**\n\n"
                )
                final_desc += attendees_str

            embed = discord.Embed(
                title="Guitar Collecting",
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

                    with open(ROLE_DATA, "w") as f:
                        json.dump(self.bot.roles, f, indent=4)

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
    description = "Inside this box:\n**"
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
        title="Guitar Collecting",
        description=description,
        color=color,
    )
    embed.set_footer(
        text="Thank you for all the love towards dBot so far.",
        icon_url=random.choice(
            [
                "https://play-lh.googleusercontent.com/rIXS52p6GQdcbGBVt-Dx9YPn1Ugw_rBKpGa_RPSdXZTlmn2RNgfaUcadCtMkk_FFXw=w240-h480-rw",
                "https://play-lh.googleusercontent.com/4qD5l7VYcXU5qekefQWJpQvQJhP0GFTWGNseLFJLBhpcZigivkn7VtL_NTNJiKjxvQ=w240-h480-rw",
                "https://play-lh.googleusercontent.com/yNCP_M08pT4Altfzmi6IMWnuTRtyvrmNniK-gYhLgEqRaN309ei0lfbkbNOOwWqtZw=w240-h480-rw",
                "https://play-lh.googleusercontent.com/W4-nuXmFzL7D-tLQW3wXKvQccNoVr_Umzt-0A0eSWUVGm5Crm6TZr75-8qjfBi7wUZ8=w240-h480-rw",
            ]
        ),
    )
    return embed


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Pinata(bot))
