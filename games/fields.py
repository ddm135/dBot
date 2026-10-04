"""Column and field names the code reads from the game tables, in one place."""

# The language columns of LocaleData the bot keeps and searches.
LOCALE_COLUMNS = ("enUS", "koKR", "jaJP", "jpJP", "zhTW")

# MusicData fields naming a song's chart, by difficulty.
DIFFICULTY_FIELDS = {"Easy": "seqEasy", "Normal": "seqNormal", "Hard": "seqHard"}

# Fields of each table that name a file (a catalog key, a URL, or a code in URLs).
FILE_FIELDS: dict[str, tuple[str, ...]] = {
    "GroupData": ("emblemImage",),
    "MusicData": ("album", "image", *DIFFICULTY_FIELDS.values()),
    "SeqData": ("seqPath",),
}

# Orders in which a game shows its names (the first language that has one).
ENGLISH_FIRST = ("enUS", "koKR", "jaJP", "jpJP")
KOREAN_FIRST = ("koKR", "enUS", "jaJP", "jpJP")
JAPANESE_FIRST = ("jaJP", "jpJP", "enUS", "koKR")
