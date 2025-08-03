from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from statics.types import GameDetails

LOCK = Path(".dBot")

TEST_GUILD = 540849436868214784
SSRG_GUILD = 360109303199432704
STATUS_CHANNEL = 1335315390732963952
OWNER_ID = 180925261531840512

MAX_RETRIES = 10
MAX_AUTOCOMPLETE = 25

BONUS_OFFSET = timedelta(days=1)
RESET_OFFSET = timedelta(hours=2)

TIMEZONES = {
    "KST": ZoneInfo("Asia/Seoul"),
    "JST": ZoneInfo("Asia/Tokyo"),
    "CST": ZoneInfo("Asia/Taipei"),
    # "EST": ZoneInfo("Etc/GMT-5"),
    # "EDT": ZoneInfo("Etc/GMT-4"),
    "PHT": ZoneInfo("Asia/Manila"),
    # "ICT": ZoneInfo("Asia/Bangkok"),
}

STATIC_MODULES = (
    "statics.consts",
    "statics.types",
)

EXTENSIONS = (
    "helpers.cryptographic",
    "helpers.google_sheets",
    "helpers.google_drive",
    "helpers.superstar",
    "commands.administrative",
    "tasks.dalcom_sync",
    "tasks.info_sync",
    "tasks.pin_ssleague",
    "app_commands.info",
    "app_commands.ssleague",
    "tasks.bonus_sync",
    "tasks.notify_bonus",
    "app_commands.bonus",
    "tasks.data_sync",
    "app_commands.ping",
    "app_commands.role",
    "tasks.clock",
    "commands.miscellaneous",
    # "entertainment.pinata",
    "events.on_command_error",
    "events.on_message",
    "events.on_ready",
)


class AssetScheme(Enum):
    JSON = 1
    DIRECT = 2
    BUNDLE = 3


GAMES: dict[str, "GameDetails"] = {
    "SM": {
        "name": "SUPERSTAR SM",
        "infoSpreadsheet": "1dX_5lWxenT7CDVXpgyScTHDiwazUZIO3441RaNpN55g",
        "infoReplaceGrid": {
            "sheetId": 0,
            "startRowIndex": 1,
            "startColumnIndex": 1,
            "endColumnIndex": 2,
        },
        "infoRange": "Songs!A2:E",
        "infoColumns": (
            "song_id",
            "artist_name",
            "song_name",
            "search_term",
            "duration",
        ),
        "pingSpreadsheet": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingReplaceGrid": {
            "sheetId": 2033296248,
            "startRowIndex": 0,
            "startColumnIndex": 3,
            "endColumnIndex": 4,
        },
        "pingRange": "SM!B1:D",
        "pingUsers": "SM!C",
        "pingColumns": ("emblem", "users", "artist_name"),
        "bonusSpreadsheet": "1dX_5lWxenT7CDVXpgyScTHDiwazUZIO3441RaNpN55g",
        "bonusReplaceGrid": {
            "sheetId": 48988104,
            "startRowIndex": 1,
            "startColumnIndex": 2,
            "endColumnIndex": 3,
        },
        "bonusRange": "dBonuses!A2:J",
        "bonusColumns": (
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
        ),
        "color": 0xE204DD,
        "pinChannelIds": {
            SSRG_GUILD: 401291379810107394,
            TEST_GUILD: 1336210286289616917,
        },
        "pinRoles": {
            SSRG_GUILD: 420428449325252608,
            TEST_GUILD: 1350860245487845570,
        },
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["KST"],
        "manifest": "https://super-star.s3.amazonaws.com/version/{version}.txt",
        "api": "https://smtown-api-https.dalcomsoft.net",
        "authorization": "SFFINkh6ckdwRkZiRmlYeis1Mi86U1cwU0JxdWg1dw==",
        "target_audience": "864447301209-h0hsb0denh03td7sgoelh5lmdvv79f9h",
        "assetScheme": AssetScheme.DIRECT,
    },
    "JYP": {
        "name": "SUPERSTAR JYP",
        "infoSpreadsheet": "1XgaSMje3TKa1bnekWzmpLRjr81QWoag_6w9SlzSwN0g",
        "infoReplaceGrid": {
            "sheetId": 0,
            "startRowIndex": 1,
            "startColumnIndex": 1,
            "endColumnIndex": 2,
        },
        "infoRange": "Songs!A2:E",
        "infoColumns": (
            "song_id",
            "artist_name",
            "song_name",
            "search_term",
            "duration",
        ),
        "pingSpreadsheet": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingReplaceGrid": {
            "sheetId": 138125467,
            "startRowIndex": 0,
            "startColumnIndex": 3,
            "endColumnIndex": 4,
        },
        "pingRange": "JYP!B1:D",
        "pingUsers": "JYP!C",
        "pingColumns": ("emblem", "users", "artist_name"),
        "bonusSpreadsheet": "1XgaSMje3TKa1bnekWzmpLRjr81QWoag_6w9SlzSwN0g",
        "bonusReplaceGrid": {
            "sheetId": 1160780925,
            "startRowIndex": 1,
            "startColumnIndex": 2,
            "endColumnIndex": 3,
        },
        "bonusRange": "dBonuses!A2:J",
        "bonusColumns": (
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
        ),
        "color": 0x4977FB,
        "pinChannelIds": {
            SSRG_GUILD: 360109303199432705,
            TEST_GUILD: 1354222667384885329,
        },
        "pinRoles": {
            SSRG_GUILD: 420428238171668480,
        },
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["KST"],
        "manifest": (
            "https://superstar-jyp-resource.s3.amazonaws.com/version/j_{version}.txt"
        ),
        "api": "https://jypnation-api-https.dalcomsoft.net",
        "authorization": "MHhYTEhMQnV1aGpqY3ZRd1JHbUY6SlE0VFZZaVhXYw==",
        "target_audience": "506321732908-4u8t2uk3888gm8087i7lcpi97ff6ld4a",
        "assetScheme": AssetScheme.DIRECT,
    },
    "SS": {
        "name": "SUPERSTAR STARSHIP",
        "infoSpreadsheet": "13MYqeey_Pd8_5vXsEQe94usC517WaMEduPte19xtQiU",
        "infoReplaceGrid": {
            "sheetId": 0,
            "startRowIndex": 1,
            "startColumnIndex": 1,
            "endColumnIndex": 2,
        },
        "infoRange": "Songs!A2:D",
        "infoColumns": (
            "song_id",
            "artist_name",
            "song_name",
            "duration",
        ),
        "pingSpreadsheet": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingReplaceGrid": {
            "sheetId": 2107313752,
            "startRowIndex": 0,
            "startColumnIndex": 3,
            "endColumnIndex": 4,
        },
        "pingRange": "STARSHIP!B1:D",
        "pingUsers": "STARSHIP!C",
        "pingColumns": ("emblem", "users", "artist_name"),
        "bonusSpreadsheet": "13MYqeey_Pd8_5vXsEQe94usC517WaMEduPte19xtQiU",
        "bonusReplaceGrid": {
            "sheetId": 1039181707,
            "startRowIndex": 1,
            "startColumnIndex": 2,
            "endColumnIndex": 3,
        },
        "bonusRange": "Bonuses!A2:J",
        "bonusColumns": (
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
        ),
        "color": 0x484E8A,
        "pinChannelIds": {},
        "pinRoles": {},
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["KST"],
        "manifest": (
            "https://superstar-starship.s3.amazonaws.com"
            "/version/real/manifest/{version}.txt"
        ),
        "api": "https://sss-api-https.dalcomsoft.net",
        "authorization": "bnZQb1RweVg4WVlyUlZERE85Zkc6WVBrQklrNFdhcQ==",
        "target_audience": "42043845970-4hm4teclds9q4pji2on6f8o35n4ji6ac",
        "assetScheme": AssetScheme.DIRECT,
    },
    "KD": {
        "name": "SuperStar KANGDANIEL",
        "infoSpreadsheet": "1QSCRXKtiwoMTLV8knHC_o4NwV3UZM6ZvL-l9ZCPxoRM",
        "infoReplaceGrid": {},
        "infoRange": "Official Local Version!A2:E",
        "infoColumns": (
            "song_id",
            "artist_name",
            "song_name",
            "_",
            "duration",
        ),
        "pingSpreadsheet": "",
        "pingReplaceGrid": {},
        "pingRange": "",
        "pingUsers": "",
        "pingColumns": (),
        "bonusSpreadsheet": "",
        "bonusReplaceGrid": {},
        "bonusRange": "",
        "bonusColumns": (),
        "color": 0xB72476,
        "pinChannelIds": {},
        "pinRoles": {},
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["KST"],
        "manifest": (
            "https://superstar-kangdaniel.s3.amazonaws.com"
            "/version/real/manifest/{version}.txt"
        ),
        "api": "",
        "authorization": "",
        "target_audience": "",
        "assetScheme": AssetScheme.JSON,
    },
    "ATZ": {
        "name": "SUPERSTAR ATEEZ",
        "infoSpreadsheet": "1ZRfm1D2sxV183umOvK4hdWUXIVWvd-Gc8nmRbnsmajY",
        "infoReplaceGrid": {},
        "infoRange": "Info!A2:G",
        "infoColumns": (
            "song_id",
            "_",
            "artist_name",
            "_",
            "_",
            "song_name",
            "duration",
        ),
        "pingSpreadsheet": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingReplaceGrid": {
            "sheetId": 1373177550,
            "startRowIndex": 0,
            "startColumnIndex": 3,
            "endColumnIndex": 4,
        },
        "pingRange": "ATEEZ!B1:D",
        "pingUsers": "ATEEZ!C",
        "pingColumns": ("emblem", "users", "artist_name"),
        "bonusSpreadsheet": "1ZRfm1D2sxV183umOvK4hdWUXIVWvd-Gc8nmRbnsmajY",
        "bonusReplaceGrid": {
            "sheetId": 0,
            "startRowIndex": 1,
            "startColumnIndex": 2,
            "endColumnIndex": 3,
        },
        "bonusRange": "Info!A2:J",
        "bonusColumns": (
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
        ),
        "color": 0xDB811C,
        "pinChannelIds": {},
        "pinRoles": {},
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["KST"],
        "manifest": (
            "https://superstar-ateez.s3.amazonaws.com"
            "/version/real/manifest/{version}.txt"
        ),
        "api": "https://ssat-api-https.dalcomsoft.net",
        "authorization": "QWVob3JZcmxGanJ2dmRtTXY4S0w6SVJLR0lqTlRyRw==",
        "target_audience": "832096356756-6nust6ofm2hfoima94nd93uakqq44ev8",
        "assetScheme": AssetScheme.BUNDLE,
    },
    "SC": {
        "name": "SUPERSTAR STAYC",
        "infoSpreadsheet": "1zEBkb3oAqP_VkilWfJt6x0nfcrweVn7Ray--wNHqxjg",
        "infoReplaceGrid": {},
        "infoRange": "Info!A2:G",
        "infoColumns": (
            "song_id",
            "_",
            "artist_name",
            "_",
            "_",
            "song_name",
            "duration",
        ),
        "pingSpreadsheet": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingReplaceGrid": {
            "sheetId": 1795572100,
            "startRowIndex": 0,
            "startColumnIndex": 3,
            "endColumnIndex": 4,
        },
        "pingRange": "STAYC!B1:D",
        "pingUsers": "STAYC!C",
        "pingColumns": ("emblem", "users", "artist_name"),
        "bonusSpreadsheet": "1zEBkb3oAqP_VkilWfJt6x0nfcrweVn7Ray--wNHqxjg",
        "bonusReplaceGrid": {
            "sheetId": 0,
            "startRowIndex": 1,
            "startColumnIndex": 2,
            "endColumnIndex": 3,
        },
        "bonusRange": "Info!A2:J",
        "bonusColumns": (
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
        ),
        "color": 0x210630,
        "pinChannelIds": {},
        "pinRoles": {},
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["KST"],
        "manifest": (
            "https://superstar-stayc.s3.amazonaws.com"
            "/version/real/manifest/{version}.txt"
        ),
        "api": "https://api-https.sssc.dalcomsoft.net",
        "authorization": "WW5yI0VCPmlKM182fG5qXllrMzQ6THpULVQ3UF9dfg==",
        "target_audience": "154091709836-q1sk7hq02vi16f3v0q88uvuf6op5lenv",
        "assetScheme": AssetScheme.BUNDLE,
    },
    "W1": {
        "name": "SUPERSTAR WAKEONE",
        "infoSpreadsheet": "1HHBluEEcWmZMHjq3WlLbS9TeLfPktQ3WrfxpcgReWF0",
        "infoReplaceGrid": {},
        "infoRange": "Songs (Note Count)!A2:D",
        "infoColumns": (
            "song_id",
            "artist_name",
            "song_name",
            "duration",
        ),
        "pingSpreadsheet": "",
        "pingReplaceGrid": {},
        "pingRange": "",
        "pingUsers": "",
        "pingColumns": (),
        "bonusSpreadsheet": "",
        "bonusReplaceGrid": {},
        "bonusRange": "",
        "bonusColumns": (),
        "color": 0x4E25D1,
        "pinChannelIds": {},
        "pinRoles": {},
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["KST"],
        "manifest": (
            "https://superstar-wakeone.s3.amazonaws.com"
            "/version/real/manifest/{version}.txt"
        ),
        "api": "https://sswo-api-https.dalcomsoft.net",
        "authorization": "",
        "target_audience": "259379396797-tfc19vpi39fosa2sic420po6l67p9ltu",
        "assetScheme": AssetScheme.BUNDLE,
    },
    "SMTOWN": {
        "name": "SUPERSTAR SMTOWN (JP/TW)",
        "infoSpreadsheet": "1kC38CLFd6xkDXD9qLHgnnv3s3jmM_4vf4RLsWuXs9NU",
        "infoReplaceGrid": {
            "sheetId": 0,
            "startRowIndex": 1,
            "startColumnIndex": 1,
            "endColumnIndex": 2,
        },
        "infoRange": "Songs!A2:E",
        "infoColumns": (
            "song_id",
            "artist_name",
            "song_name",
            "search_term",
            "duration",
        ),
        "pingSpreadsheet": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingReplaceGrid": {
            "sheetId": 755434019,
            "startRowIndex": 0,
            "startColumnIndex": 3,
            "endColumnIndex": 4,
        },
        "pingRange": "SMTOWN!B1:D",
        "pingUsers": "SMTOWN!C",
        "pingColumns": ("emblem", "users", "artist_name"),
        "bonusSpreadsheet": "1kC38CLFd6xkDXD9qLHgnnv3s3jmM_4vf4RLsWuXs9NU",
        "bonusReplaceGrid": {
            "sheetId": 1118940800,
            "startRowIndex": 1,
            "startColumnIndex": 2,
            "endColumnIndex": 3,
        },
        "bonusRange": "Bonuses!A2:J",
        "bonusColumns": (
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
        ),
        "color": 0xE10989,
        "pinChannelIds": {
            SSRG_GUILD: 481907573948153857,
            TEST_GUILD: 1343840449357418516,
        },
        "pinRoles": {},
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["JST"],
        "manifest": (
            "https://superstar-smtown-real.s3.amazonaws.com/version/{version}.txt"
        ),
        "api": "http://ss-sm-api-real.superstarsmtown.jp",
        "authorization": "",
        "target_audience": "28835016655-choauh766oss3ht8ddqiamavvtfm05ur",
        "assetScheme": AssetScheme.DIRECT,
    },
    "JYPNATION": {
        "name": "SUPERSTAR JYPNATION (JP)",
        "infoSpreadsheet": "1eVjwi0GudyMixnZtam8TeupRd3DQ6mheyRKp2lDA6qw",
        "infoReplaceGrid": {
            "sheetId": 1514100857,
            "startRowIndex": 1,
            "startColumnIndex": 1,
            "endColumnIndex": 2,
        },
        "infoRange": "Songs!A2:F",
        "infoColumns": (
            "song_id",
            "artist_name",
            "song_name",
            "search_term",
            "duration",
            "skills",
        ),
        "pingSpreadsheet": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingReplaceGrid": {
            "sheetId": 735198271,
            "startRowIndex": 0,
            "startColumnIndex": 3,
            "endColumnIndex": 4,
        },
        "pingRange": "JYPNATION!B1:D",
        "pingUsers": "JYPNATION!C",
        "pingColumns": ("emblem", "users", "artist_name"),
        "bonusSpreadsheet": "1eVjwi0GudyMixnZtam8TeupRd3DQ6mheyRKp2lDA6qw",
        "bonusReplaceGrid": {
            "sheetId": 1285084831,
            "startRowIndex": 1,
            "startColumnIndex": 2,
            "endColumnIndex": 3,
        },
        "bonusRange": "Bonuses!A2:J",
        "bonusColumns": (
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
        ),
        "color": 0x2377E4,
        "pinChannelIds": {
            SSRG_GUILD: 951350075190313010,
            TEST_GUILD: 1335936325685084242,
        },
        "pinRoles": {},
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["JST"],
        "manifest": (
            "https://superstar-jyp-jp-real.s3.amazonaws.com"
            "/version/manifest/{version}.txt"
        ),
        "api": "https://ss-jyp-api-real.superstarjyp.jp",
        "authorization": "",
        "target_audience": "776124120237-r7q2lcrob52mp0asch12hbmkd52elej5",
        "assetScheme": AssetScheme.JSON,
    },
    "LP": {
        "name": "SUPERSTAR LAPONE",
        "infoSpreadsheet": "1Ng57BGCDj025bxwCBbQulYFhRjS5runy5HnbStY_xSw",
        "infoReplaceGrid": {
            "sheetId": 0,
            "startRowIndex": 1,
            "startColumnIndex": 1,
            "endColumnIndex": 2,
        },
        "infoRange": "Songs!A2:F",
        "infoColumns": (
            "song_id",
            "artist_name",
            "song_name",
            "search_term",
            "duration",
            "skills",
        ),
        "pingSpreadsheet": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingReplaceGrid": {
            "sheetId": 0,
            "startRowIndex": 0,
            "startColumnIndex": 3,
            "endColumnIndex": 4,
        },
        "pingRange": "LAPONE!B1:D",
        "pingUsers": "LAPONE!C",
        "pingColumns": ("emblem", "users", "artist_name"),
        "bonusSpreadsheet": "1Ng57BGCDj025bxwCBbQulYFhRjS5runy5HnbStY_xSw",
        "bonusReplaceGrid": {
            "sheetId": 126522384,
            "startRowIndex": 1,
            "startColumnIndex": 2,
            "endColumnIndex": 3,
        },
        "bonusRange": "Bonuses!A2:J",
        "bonusColumns": (
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
        ),
        "color": 0xEAA715,
        "pinChannelIds": {
            SSRG_GUILD: 1039132737979813908,
            TEST_GUILD: 1340868523957813348,
        },
        "pinRoles": {},
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["JST"],
        "manifest": (
            "https://superstar-lapone-jp-real.s3.amazonaws.com"
            "/version/manifest/{version}.txt"
        ),
        "api": "https://ss-lapone-api-real.superstarlapone.jp",
        "authorization": "",
        "target_audience": "668693032380-fmhat079lhao0o335ov5uk4jkl6kget6",
        "assetScheme": AssetScheme.JSON,
    },
    "EB": {
        "name": "SUPERSTAR EBiDAN",
        "infoSpreadsheet": "1uwLl0MQM895xI4iBmdP-eVVn7HKOBisFaQCCjzJL4GQ",
        "infoReplaceGrid": {},
        "infoRange": "Songs!A2:E",
        "infoColumns": (
            "song_id",
            "artist_name",
            "song_name",
            "search_term",
            "duration",
        ),
        "pingSpreadsheet": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingReplaceGrid": {
            "sheetId": 1872493199,
            "startRowIndex": 0,
            "startColumnIndex": 3,
            "endColumnIndex": 4,
        },
        "pingRange": "EBiDAN!B1:D",
        "pingUsers": "EBiDAN!C",
        "pingColumns": ("emblem", "users", "artist_name"),
        "bonusSpreadsheet": "1uwLl0MQM895xI4iBmdP-eVVn7HKOBisFaQCCjzJL4GQ",
        "bonusReplaceGrid": {
            "sheetId": 1685871960,
            "startRowIndex": 1,
            "startColumnIndex": 2,
            "endColumnIndex": 3,
        },
        "bonusRange": "Bonuses!A2:J",
        "bonusColumns": (
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
        ),
        "color": 0xC71D1B,
        "pinChannelIds": {},
        "pinRoles": {},
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["JST"],
        "manifest": (
            "https://superstar-ebidan-jp-real.s3.amazonaws.com"
            "/version/manifest/{version}.txt"
        ),
        "api": "https://ss-ebidan-api-real.superstarebidan.jp",
        "authorization": "",
        "target_audience": "1006848262784-luosgb8o1hrjvbu6v8mjgh35b5oiimli",
        "assetScheme": AssetScheme.JSON,
    },
    "PH": {
        "name": "SuperStar Philippines",
        "infoSpreadsheet": "1Fz71pl3YCUIbCRcZRuKBjsDT4JEW0m9Uoj8wyJhUMOc",
        "infoReplaceGrid": {},
        "infoRange": "Songs!A2:E",
        "infoColumns": (
            "song_id",
            "artist_name",
            "song_name",
            "search_term",
            "duration",
        ),
        "pingSpreadsheet": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingReplaceGrid": {
            "sheetId": 564410793,
            "startRowIndex": 0,
            "startColumnIndex": 3,
            "endColumnIndex": 4,
        },
        "pingRange": "Philippines!B1:D",
        "pingUsers": "Philippines!C",
        "pingColumns": ("emblem", "users", "artist_name"),
        "bonusSpreadsheet": "1Fz71pl3YCUIbCRcZRuKBjsDT4JEW0m9Uoj8wyJhUMOc",
        "bonusReplaceGrid": {
            "sheetId": 0,
            "startRowIndex": 1,
            "startColumnIndex": 2,
            "endColumnIndex": 3,
        },
        "bonusRange": "Bonuses!A2:J",
        "bonusColumns": (
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
        ),
        "color": 0x04102D,
        "pinChannelIds": {},
        "pinRoles": {},
        "dateFormat": "%d-%m-%Y",
        "timezone": TIMEZONES["PHT"],
        "manifest": (
            "https://superstar-philippines.s3.amazonaws.com"
            "/version/real/manifest/{version}.txt"
        ),
        "api": "https://ssph-api-https.dalcomsoft.net",
        "authorization": "WWFeNnhxVldSJWFkVWp4Z3ViOFY6WmJRcy1uZ1YyQQ==",
        "target_audience": "234980834479-creie63p99odjttcv9pvifjelsuf983i",
        "assetScheme": AssetScheme.JSON,
    },
}

ROLES: dict[int, tuple[int, ...]] = {
    TEST_GUILD: (1341036401483055147, 1341036445900472403, 1341036487084609556),
    SSRG_GUILD: (
        437796301401489420,  # Swain
        459083923327025154,  # fromis_9
        506486523345108993,  # BAEK A YEON
        485894758867271709,  # woo!ah!
        452938514221367298,  # SHINee
        467093328819912724,  # f(x)
        499537948274982922,  # ATEEZ
        478013408781008896,  # NCT DREAM
        443941784066719744,  # NCT
        481401571108716544,  # 3RACHA
        492037142718185473,  # STRAY KIDS
        467358853936185364,  # BIGBANG
        434407852719996938,  # LOOΠΔ
        425779125773664267,  # TWICE
        463295473206165505,  # GOT7
        473350382421016586,  # DAY6
        433044172623052800,  # TVXQ!
        432952370314477578,  # SUPER JUNIOR
        431187380188479508,  # ITZY
        434935025767809024,  # EXO
        486984842886512647,  # WONDER GIRLS
        434568293848711168,  # Red Velvet
        497585329113399336,  # CHUNGHA
        491962322974408736,  # BLACKPINK
        464521299885031435,  # IU
        436712096604880907,  # BTS
        498995602391171085,  # Agust D
        481700836829822997,  # TXT
        474593959226638347,  # EXO-CBX
        438837118697996299,  # MAMAMOO
        479773267247235082,  # JAMIE
        443544890622738433,  # PRISTIN V
        436930802715066368,  # SuperM
        446958971471790080,  # DREAMCATCHER
        454021810720210956,  # SEVENTEEN
        457396413639426048,  # NU'EST
        461181565821517825,  # MONSTA X
        462785070877638657,  # GIRLS' GENERATION
        471052244264157204,  # JJ Project
        470103655656194068,  # IZ*ONE
        475640605087891467,  # WJSN
        480072838842417152,  # HYOLYN
        481013464039555082,  # 2PM
        488063679552552971,  # GFriend
        467556568960073729,  # HYUNA
        490995416188321824,  # GOLDEN CHILD
        493777070120370178,  # iKON
        494436432274784256,  # OH MY GIRL
        497655139478274058,  # SUZY
        523502228078592001,  # TAEYEON
        528972207922348032,  # Oh!GG
        455139836953755648,  # SUNMI
        460246887899856896,  # DAY6 (Even of Day)
        939391654220148748,  # KANG DANIEL
        939397127099019284,  # PSY
        939398862886567976,  # THE BOYZ
        965022365601910784,  # CLASS:y
        1105405311436726313,  # STAYC
    ),
}
