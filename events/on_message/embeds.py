import discord


class WordPingEmbed(discord.Embed):
    def __init__(
        self,
        word: str,
        message: discord.Message,
    ) -> None:
        assert message.guild
        description = (
            f"`{message.author.name}` mentioned `{word}` in "
            f"<#{message.channel.id}> on "
            f"<t:{int(message.created_at.timestamp())}:f>\n\n"
            f"{message.content}"
        )
        if len(description) > 4096:
            description = description[:4093] + "..."
        super().__init__(
            description=description,
            color=message.author.color,
        )
        self.set_author(
            name=f"Word Ping in {message.guild.name}",
            url=message.jump_url,
            icon_url=message.guild.icon.url if message.guild.icon else None,
        )
        self.set_footer(
            text="Click title to jump to message",
        )
        self.set_thumbnail(url=message.author.display_avatar.url)
