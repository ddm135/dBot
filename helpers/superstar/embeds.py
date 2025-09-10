from datetime import datetime
from pathlib import Path

import discord


class SSLeagueEmbed(discord.Embed):
    def __init__(
        self,
        artist_name: str,
        song_name: str,
        duration: str,
        album: str | Path | None,
        icon: str | Path | None,
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
                f"**{(artist_name.replace(r"*", r"\*").replace(r"_", r"\_")
                      .replace(r"`", r"\`"))} - "
                f"{(song_name.replace(r"*", r"\*").replace(r"_", r"\_")
                    .replace(r"`", r"\`"))}**"
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

        self.set_thumbnail(
            url=(f"attachment://{album.name}" if isinstance(album, Path) else album)
        )
        self.set_footer(
            text=(
                f"{current_time.strftime("%A, %B %d, %Y").replace(" 0", " ")}"
                f" · Pinned by {user_name}"
            ),
            icon_url=(f"attachment://{icon.name}" if isinstance(icon, Path) else icon),
        )
