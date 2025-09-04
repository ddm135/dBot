from datetime import datetime

import discord


class SSLeagueEmbed(discord.Embed):
    def __init__(
        self,
        artist_name: str,
        song_name: str,
        duration: str,
        album: str | discord.File | None,
        icon: str | discord.File | None,
        color: int,
        skills: str | None,
        current_time: datetime,
        user_name: str,
        artist_last: datetime | None = None,
        song_last: datetime | None = None,
    ) -> None:
        super().__init__(
            title=f"SSL #{current_time.strftime("%u")}",
            description=(
                f"**{artist_name.replace(r"*", r"\*").replace(r"_", r"\_")} - "
                f"{song_name.replace(r"*", r"\*").replace(r"_", r"\_")}**"
            ),
            color=color,
        )

        self.add_field(name="Duration", value=duration)
        if skills:
            self.add_field(name="Skill Order", value=skills)

        self.add_field(
            name="Artist Last Appearance",
            value=(
                f"{artist_last.strftime("%A, %B %d, %Y").replace(" 0", " ")} "
                f"(<t:{int(artist_last.timestamp())}:R>)"
                if artist_last is not None
                else "N/A"
            ),
            inline=False,
        )
        self.add_field(
            name="Song Last Appearance",
            value=(
                f"{song_last.strftime("%A, %B %d, %Y").replace(" 0", " ")} "
                f"(<t:{int(song_last.timestamp())}:R>)"
                if song_last is not None
                else "N/A"
            ),
            inline=False,
        )

        print(album, icon)

        self.set_thumbnail(
            url=(
                f"attachment://{album.filename}"
                if isinstance(album, discord.File)
                else album
            )
        )
        self.set_footer(
            text=(
                f"{current_time.strftime("%A, %B %d, %Y").replace(" 0", " ")}"
                f" · Pinned by {user_name}"
            ),
            icon_url=(
                f"attachment://{icon.filename}"
                if isinstance(icon, discord.File)
                else icon
            ),
        )
