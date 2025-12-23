from datetime import datetime
from pathlib import Path

import discord

from statics.consts import GAMES


class SSLeagueEmbed(discord.Embed):
    def __init__(
        self,
        game: str,
        artist_name: str,
        song_name: str,
        duration: str,
        note_count: dict,
        album: str | Path | None,
        icon: str | Path | None,
        color: int,
        skills: str | None,
        current_time: datetime,
        username: str,
        artist_last: datetime | None = None,
        song_last: datetime | None = None,
    ) -> None:
        super().__init__(
            title=artist_name.replace(r"*", r"\*")
            .replace(r"_", r"\_")
            .replace(r"`", r"\`"),
            description=f"**{(song_name.replace(r"*", r"\*").replace(r"_", r"\_")
                              .replace(r"`", r"\`"))}**",
            color=color,
        )

        self.set_author(
            name=f"{GAMES[game]["name"]} - SSL #{current_time.strftime("%u")}",
            icon_url="attachment://icon.png" if isinstance(icon, Path) else icon,
        )
        self.set_thumbnail(
            url="attachment://album.png" if isinstance(album, Path) else album
        )

        self.add_field(name="Duration", value=duration)
        self.add_field(
            name="Note Count",
            value=" / ".join(
                str(difficulty["count"]) for difficulty in note_count.values()
            ),
        )
        if skills:
            self.add_field(name="Skill Order", value=skills, inline=False)

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

        self.set_footer(
            text=(
                f"{current_time.strftime("%A, %B %d, %Y").replace(" 0", " ")}"
                f" · Pinned by {username}"
            ),
        )
