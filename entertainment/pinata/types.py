from typing import TypedDict

import discord


class PinataDetails(TypedDict):
    role: discord.Role | str
    of: str
    mention: str
    label: str
