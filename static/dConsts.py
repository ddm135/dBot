from datetime import timedelta
from zoneinfo import ZoneInfo

from static.dTypes import GameDetails

TEST_GUILD = 540849436868214784
STATUS_CHANNEL = 1335315390732963952
MAX_AUTOCOMPLETE_RESULTS = 25

OK_ROLE_OWNER = 973231666711634001
SSRG_ROLE_MOD = 1039013749597683742
SSRG_ROLE_SS = 439095346061377536

AESKey = "WnFKN1v_gUcgmUVZnjjjGXGwk557zBSO"
A_JSON_HEADERS = {
    "X-SuperStar-AES-IV": "PUIEOQYGNEFFFUAX",
    "X-SuperStar-Asset-Ignore": "true",
    "X-SuperStar-API-Version": "8",
}
A_JSON_BODY = (
    "/OBWvurTOUC41Z8AbFs6LbFZ6vZZSLpHL+SXK4yVJ4yT"
    "+FQDGqcb8Vy51zOBdtzgUYHWzeN0LAWE6Mll+Kpb3w=="
)

TIMEZONES = {
    "KST": ZoneInfo("Asia/Seoul"),
    "JST": ZoneInfo("Asia/Tokyo"),
    "PHT": ZoneInfo("Asia/Manila"),
    "ICT": ZoneInfo("Asia/Bangkok"),
}

EXTENSIONS = [
    "commands.administrative",
    "commands.memes",
    "app_commands.bonus",
    "app_commands.ssLeague",
    "tasks.clock",
    "tasks.notify_p8",
    "tasks.notify_p9",
]

GAMES: dict[str, GameDetails] = {
    "JYP_JP": {
        "name": "SUPERSTAR JYPNATION (JP)",
        "sslId": "1eVjwi0GudyMixnZtam8TeupRd3DQ6mheyRKp2lDA6qw",
        "sslRange": "Songs!A2:F",
        "sslColumns": [
            "song_id",
            "artist_name",
            "song_name",
            "duration",
            "image",
            "skills",
        ],
        "sslOffset": timedelta(hours=2),
        "pingId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingRange": "JYPNATION!A1:D",
        "pingWrite": "JYPNATION!C",
        "pingColumns": ["artist_name", "emblem", "users"],
        "bonusId": "1eVjwi0GudyMixnZtam8TeupRd3DQ6mheyRKp2lDA6qw",
        "bonusRange": "Bonuses!A2:J",
        "bonusColumns": [
            "song_id",
            "bonus_amount",
            "artist_name",
            "member_name",
            "album_name",
            "song_name",
            "duration",
            "bonus_date",
            "bonus_start",
            "bonus_end",
        ],
        "color": 0x1A6DE1,
        "pinChannelId": 1335936325685084242,
        "api": "https://ss-jyp-api-real.superstarjyp.jp",
        "timezone": TIMEZONES["JST"],
    },
    "LP": {
        "name": "SUPERSTAR LAPONE",
        "sslId": "1Ng57BGCDj025bxwCBbQulYFhRjS5runy5HnbStY_xSw",
        "sslRange": "Songs!A2:F",
        "sslColumns": [
            "song_id",
            "artist_name",
            "song_name",
            "duration",
            "image",
            "skills",
        ],
        "sslOffset": timedelta(hours=2),
        "pingId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingRange": "LAPONE!A1:D",
        "pingWrite": "LAPONE!C",
        "pingColumns": ["artist_name", "emblem", "users"],
        "bonusId": "1Ng57BGCDj025bxwCBbQulYFhRjS5runy5HnbStY_xSw",
        "bonusRange": "Bonuses!A2:J",
        "bonusColumns": [
            "song_id",
            "bonus_amount",
            "artist_name",
            "member_name",
            "album_name",
            "song_name",
            "duration",
            "bonus_date",
            "bonus_start",
            "bonus_end",
        ],
        "color": 0xFF9700,
        "pinChannelId": 1336210286289616917,
        "api": "https://ss-lapone-api-real.superstarlapone.jp",
        "timezone": TIMEZONES["JST"],
    },
    "EB": {
        "name": "SUPERSTAR EBiDAN",
        "sslId": None,
        "sslRange": None,
        "sslColumns": None,
        "sslOffset": None,
        "pingId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingRange": "EBiDAN!A1:D",
        "pingWrite": "EBiDAN!C",
        "pingColumns": ["artist_name", "emblem", "users"],
        "bonusId": "1uwLl0MQM895xI4iBmdP-eVVn7HKOBisFaQCCjzJL4GQ",
        "bonusRange": "Bonuses!A2:J",
        "bonusColumns": [
            "song_id",
            "bonus_amount",
            "artist_name",
            "member_name",
            "album_name",
            "song_name",
            "duration",
            "bonus_date",
            "bonus_start",
            "bonus_end",
        ],
        "color": 0x960C19,
        "pinChannelId": None,
        "api": "https://ss-ebidan-api-real.superstarebidan.jp",
        "timezone": TIMEZONES["JST"],
    },
    "PH": {
        "name": "SuperStar Philippines",
        "sslId": None,
        "sslRange": None,
        "sslColumns": None,
        "sslOffset": None,
        "pingId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingRange": "Philippines!A1:D",
        "pingWrite": "Philippines!C",
        "pingColumns": ["artist_name", "emblem", "users"],
        "bonusId": "1Fz71pl3YCUIbCRcZRuKBjsDT4JEW0m9Uoj8wyJhUMOc",
        "bonusRange": "Bonuses!A2:J",
        "bonusColumns": [
            "song_id",
            "bonus_amount",
            "artist_name",
            "member_name",
            "album_name",
            "song_name",
            "duration",
            "bonus_date",
            "bonus_start",
            "bonus_end",
        ],
        "color": 0x071543,
        "pinChannelId": None,
        "api": "https://ssph-api-https.dalcomsoft.net/",
        "timezone": TIMEZONES["PHT"],
    },
}
