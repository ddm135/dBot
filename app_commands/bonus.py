import discord
from discord import app_commands
from discord.ext import commands

from app_commands.autocomplete.bonus import artist_autocomplete
from static.dConsts import GAMES, sheetService


class Bonus(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        description=(
            "Add an artist to the bonus ping list (1 hour "
            "before bonus starts, 1 day 1 hour before bonus ends)"
        )
    )
    @app_commands.autocomplete(artist_name=artist_autocomplete)
    @app_commands.choices(
        game=[app_commands.Choice(name=v["name"], value=k) for k, v in GAMES.items()]
    )
    async def bonus_add(
        self, itr: discord.Interaction, game: app_commands.Choice[str], artist_name: str
    ):
        await itr.response.defer(ephemeral=True)
        gameD = GAMES[game.value]
        result = (
            sheetService.values()
            .get(
                spreadsheetId=gameD["pingId"],
                range=gameD["pingRange"],
            )
            .execute()
        )
        pings = result.get("values", [])
        msg = None
        ping_list = []
        for i, ping in enumerate(pings, start=1):
            if (
                ping[gameD["pingColumns"].index("artist_name")].lower()
                == artist_name.lower()
            ):
                if len(ping) < len(gameD["pingColumns"]) or (
                    str(itr.user.id)
                    not in (
                        ping_list := ping[gameD["pingColumns"].index("users")].split(
                            ","
                        )
                    )
                ):
                    ping_list.append(str(itr.user.id))
                    ping_str = ",".join(ping_list)
                    write_location = f"{gameD["pingWrite"]}{i}"
                    sheetService.values().update(
                        spreadsheetId=gameD["pingId"],
                        range=write_location,
                        valueInputOption="RAW",
                        body={"values": [[ping_str]]},
                    ).execute()
                    msg = await itr.followup.send(
                        f"Added to {ping[gameD['pingColumns'].index('artist_name')]} "
                        "ping list!",
                        wait=True,
                    )
                else:
                    msg = await itr.followup.send(
                        f"Already in {ping[gameD['pingColumns'].index('artist_name')]} "
                        "ping list!",
                        wait=True,
                    )
                break
        if not msg:
            await itr.followup.send(
                f"{artist_name} is not a valid artist for {game.name}"
            )

    @app_commands.command(description="Remove an artist from the bonus ping list")
    @app_commands.autocomplete(artist_name=artist_autocomplete)
    @app_commands.choices(
        game=[app_commands.Choice(name=v["name"], value=k) for k, v in GAMES.items()]
    )
    async def bonus_remove(
        self, itr: discord.Interaction, game: app_commands.Choice[str], artist_name: str
    ):
        await itr.response.defer(ephemeral=True)
        gameD = GAMES[game.value]
        result = (
            sheetService.values()
            .get(
                spreadsheetId=gameD["pingId"],
                range=gameD["pingRange"],
            )
            .execute()
        )
        pings = result.get("values", [])
        msg = None
        for i, ping in enumerate(pings, start=1):
            if (
                ping[gameD["pingColumns"].index("artist_name")].lower()
                == artist_name.lower()
            ):
                if len(ping) == len(gameD["pingColumns"]) and (
                    str(itr.user.id)
                    in (
                        ping_list := ping[gameD["pingColumns"].index("users")].split(
                            ","
                        )
                    )
                ):
                    ping_list.remove(str(itr.user.id))
                    ping_str = ",".join(ping_list)
                    write_location = f"{gameD["pingWrite"]}{i}"
                    sheetService.values().update(
                        spreadsheetId=gameD["pingId"],
                        range=write_location,
                        valueInputOption="RAW",
                        body={"values": [[ping_str]]},
                    ).execute()
                    msg = await itr.followup.send(
                        f"Removed from "
                        f"{ping[gameD['pingColumns'].index('artist_name')]} ping list!",
                        wait=True,
                    )
                else:
                    msg = await itr.followup.send(
                        f"Already not in "
                        f"{ping[gameD['pingColumns'].index('artist_name')]} ping list!",
                        wait=True,
                    )
                break
        if not msg:
            await itr.followup.send(
                f"{artist_name} is not a valid artist for {game.name}"
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Bonus(bot))
