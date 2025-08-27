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
    "tasks.basic_sync",
    "tasks.dalcom_sync",
    "tasks.info_sync",
    "tasks.pin_ssleague",
    "app_commands.info",
    "app_commands.ssleague",
    "tasks.bonus_sync",
    "tasks.notify_bonus",
    "app_commands.bonus",
    "tasks.emblem_sync",
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


class Data(Enum):
    CREDENTIALS = Path("data/credentials.json")
    WORD_PINGS = Path("data/word_pings.json")
    ROLES = Path("data/roles.json")
    SSLEAGUES = Path("data/ssleagues.json")
    LAST_MODIFIED = Path("data/last_modified.json")


class InfoColumns(Enum):
    SSL = (
        "song_id",
        "artist_name",
        "song_name",
        "search_term",
        "duration",
    )
    NO_SSL = (
        "song_id",
        "artist_name",
        "song_name",
        "duration",
    )
    SSL_WITH_SKILLS = (
        "song_id",
        "artist_name",
        "song_name",
        "search_term",
        "duration",
        "skills",
    )
    SHARED = (
        "song_id",
        "_",
        "artist_name",
        "_",
        "_",
        "song_name",
        "duration",
    )


BONUS_COLUMNS = (
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
)
PING_COLUMNS = ("users", "artist_name")
EMBLEM_COLUMNS = ("artist_name", "emblem")


class AssetScheme(Enum):
    JSON_URL = 1
    DIRECT_URL = 2
    JSON_CATALOG = 3
    BINARY_CATALOG = 4


GAMES: dict[str, "GameDetails"] = {
    "SM": {
        "name": "SUPERSTAR SM",
        "color": 0xE204DD,
        "info": {
            "spreadsheetId": "1dX_5lWxenT7CDVXpgyScTHDiwazUZIO3441RaNpN55g",
            "replaceGrid": {
                "sheetId": 0,
                "startRowIndex": 1,
                "startColumnIndex": 1,
                "endColumnIndex": 2,
            },
            "range": "Songs!A2:E",
            "columns": InfoColumns.SSL.value,
        },
        "bonus": {
            "spreadsheetId": "1dX_5lWxenT7CDVXpgyScTHDiwazUZIO3441RaNpN55g",
            "range": "dBonuses!A2:J",
            "columns": BONUS_COLUMNS,
            "replaceGrid": {
                "sheetId": 48988104,
                "startRowIndex": 1,
                "startColumnIndex": 2,
                "endColumnIndex": 3,
            },
        },
        "ping": {
            "spreadsheetId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
            "range": "SM!C1:D",
            "columns": PING_COLUMNS,
            "replaceGrid": {
                "sheetId": 2033296248,
                "startRowIndex": 0,
                "startColumnIndex": 3,
                "endColumnIndex": 4,
            },
        },
        "emblem": {
            "spreadsheetId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
            "range": "SM!A1:B",
            "columns": EMBLEM_COLUMNS,
            "replaceGrid": {},
        },
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
        "lookupQuery": "id=890937532&country=kr",
        "manifestUrl": "https://super-star.s3.amazonaws.com/version/{version}.txt",
        "assetScheme": AssetScheme.DIRECT_URL,
        "authorization": "SFFINkh6ckdwRkZiRmlYeis1Mi86U1cwU0JxdWg1dw==",
        "target_audience": "864447301209-h0hsb0denh03td7sgoelh5lmdvv79f9h",
    },
    "JYP": {
        "name": "SUPERSTAR JYP",
        "color": 0x4977FB,
        "info": {
            "spreadsheetId": "1XgaSMje3TKa1bnekWzmpLRjr81QWoag_6w9SlzSwN0g",
            "replaceGrid": {
                "sheetId": 0,
                "startRowIndex": 1,
                "startColumnIndex": 1,
                "endColumnIndex": 2,
            },
            "range": "Songs!A2:E",
            "columns": InfoColumns.SSL.value,
        },
        "bonus": {
            "spreadsheetId": "1XgaSMje3TKa1bnekWzmpLRjr81QWoag_6w9SlzSwN0g",
            "range": "dBonuses!A2:J",
            "columns": BONUS_COLUMNS,
            "replaceGrid": {
                "sheetId": 1160780925,
                "startRowIndex": 1,
                "startColumnIndex": 2,
                "endColumnIndex": 3,
            },
        },
        "ping": {
            "spreadsheetId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
            "range": "JYP!C1:D",
            "columns": PING_COLUMNS,
            "replaceGrid": {
                "sheetId": 138125467,
                "startRowIndex": 0,
                "startColumnIndex": 3,
                "endColumnIndex": 4,
            },
        },
        "emblem": {
            "spreadsheetId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
            "range": "JYP!A1:B",
            "columns": EMBLEM_COLUMNS,
            "replaceGrid": {},
        },
        "pinChannelIds": {
            SSRG_GUILD: 360109303199432705,
            TEST_GUILD: 1354222667384885329,
        },
        "pinRoles": {
            SSRG_GUILD: 420428238171668480,
        },
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["KST"],
        "lookupQuery": "id=1086866467&country=kr",
        "manifestUrl": (
            "https://superstar-jyp-resource.s3.amazonaws.com/version/j_{version}.txt"
        ),
        "assetScheme": AssetScheme.DIRECT_URL,
        "authorization": "MHhYTEhMQnV1aGpqY3ZRd1JHbUY6SlE0VFZZaVhXYw==",
        "target_audience": "506321732908-4u8t2uk3888gm8087i7lcpi97ff6ld4a",
    },
    "SS": {
        "name": "SUPERSTAR STARSHIP",
        "color": 0x484E8A,
        "info": {
            "spreadsheetId": "13MYqeey_Pd8_5vXsEQe94usC517WaMEduPte19xtQiU",
            "replaceGrid": {
                "sheetId": 0,
                "startRowIndex": 1,
                "startColumnIndex": 1,
                "endColumnIndex": 2,
            },
            "range": "Songs!A2:D",
            "columns": InfoColumns.NO_SSL.value,
        },
        "bonus": {
            "spreadsheetId": "13MYqeey_Pd8_5vXsEQe94usC517WaMEduPte19xtQiU",
            "range": "Bonuses!A2:J",
            "columns": BONUS_COLUMNS,
            "replaceGrid": {
                "sheetId": 1039181707,
                "startRowIndex": 1,
                "startColumnIndex": 2,
                "endColumnIndex": 3,
            },
        },
        "ping": {
            "spreadsheetId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
            "range": "STARSHIP!C1:D",
            "columns": PING_COLUMNS,
            "replaceGrid": {
                "sheetId": 2107313752,
                "startRowIndex": 0,
                "startColumnIndex": 3,
                "endColumnIndex": 4,
            },
        },
        "emblem": {
            "spreadsheetId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
            "range": "STARSHIP!A1:B",
            "columns": EMBLEM_COLUMNS,
            "replaceGrid": {},
        },
        "pinChannelIds": {},
        "pinRoles": {},
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["KST"],
        "lookupQuery": "id=1480181152&country=kr",
        "manifestUrl": (
            "https://superstar-starship.s3.amazonaws.com"
            "/version/real/manifest/{version}.txt"
        ),
        "assetScheme": AssetScheme.BINARY_CATALOG,
        "catalogUrl": (
            "http://d1869m1xmsv4ed.cloudfront.net/assets"
            "/LIVE/iOS/catalog_{version}.bin"
        ),
        "authorization": "bnZQb1RweVg4WVlyUlZERE85Zkc6WVBrQklrNFdhcQ==",
        "target_audience": "42043845970-4hm4teclds9q4pji2on6f8o35n4ji6ac",
    },
    "KD": {
        "name": "SuperStar KANGDANIEL",
        "iconUrl": "https://lh3.googleusercontent.com/fife/ALs6j_F5p1r_gQeZEflvr7IT"
        "q6WPNV3baQB9c3WRnoXMU1tVyBWdls2WF17Fi-gRYlKERFF-RYmbP_tHqoWUdw-Qe8UQcl120g"
        "ropBajFxrOWfJDrP-6MzB_-CQpMIQMYEro_xafihKHHUS4P3nOhPaQBM1flRiQD0Rg5dw4E0fU"
        "iXNUy7chCIzPiTh7VZLF6zGlrB-uz9fMYKg_35JS_yCQv_ysZwBjmWtDmVI6Gh3sjc0EPppijC"
        "sFAXlKdLAZLm0blHtfqmxhafKVrhmq0XyHCjQ04pxw8CGOMNNTpSvd9MYQELPiPTZt2QykEj21"
        "hJ9rYzWCpyHVA3meJpeKQS7OZllbDgfh3nHlylTeq6LrWiZbaatznSbXPhEKYx2gSztUdPccsP"
        "TYr9X3c3J5HjHIhtsovYH-4LhIhO1P767BQGtflPzzZMIRvG54ARL_2THgxphjJYxILk-etoFA"
        "e35SW18w49gAporBqvcBodObPURcrB8C6jyFWZLhMCERu2jjdgDEXnYZ2n5iSy6Q04cPYYVOjI"
        "X9EDrkg18kg0vvMnkQ2VcK3kUbdqcEbi5x_-T13Uw8GDWcCyDuEe09Vmw9tMxL5N7wVyOyx9qX"
        "EYvpAp9LRS1mxRveGt-LG-pNH0EEMdGOgcMoVdEBMzWi0gJ2Zc9H82J9PXD7Zd68xZPUhiOuVE"
        "BwMbVOwKPNsR3nLAgVtUMhMNqOBWRpdWRHLd7kRo08MltORdIa4QWWJeWDHsqGmK3vb_UewDE8"
        "t2iHCCK3cPKQ5L2m9vZ1pQCln5upBHilk7-L6Oj-bpTJRDIMV78BKsSAaFyXlE_HOE28KFf4Qv"
        "7frYvm1dI6ptXc9J6dv_P-s_M6dGawGT7KY6u4rDcrhg4taiWNWTH-5qbNh6-xWpepeQ0wbMtu"
        "YPyVZV_i_BVNrMJAPl8P9UjVoEWweAlPX5uUV5nyCymDSOGU5-m1mpQi-bjSlkuFCg_0E6uy_S"
        "AD_P0SVbwFFMzNLPKps-iV0RTq-PmPHgT1OJGZ3ENQgiMa7hWW5Ef4Lv9GAfBeX7-syMJtoTO3"
        "-aboiGkauVWidEtuJItsdzqW5_4ve4kNt4SuH97EheoX2fmNcX6Z_fDILAbNkPvY3ktc8-MoqM"
        "k8zup4oFlcDK1CQwsgkiMStwPiuCkRJccPPGfyAS1za2RKsWzsU5s67L_eDE_bpSzCkMs23BXe"
        "dgjC2U_HXqOd-QPRho6c5E_-Iym46uGcAYG0ZvozetFlmnmY3VT5HjyJ34WTDKL4B4sOF2Eni2"
        "WkTKgaBAqfoXhVIO82D1fGdn_XPKPK2EOQKtAUnEzFQyTtYTFs06BeNzcn6-IQsA5Fx8kbxsZn"
        "upeo9T8IQjJ2QOxVUPgZEdpKQIi9ivV-aURpHC07F9F62kjr-ukyKwMmsOBnbNZ2ofvLyFmV33"
        "ZwrqnxzL16QskEWfWBLKx6IzxweJormHpnp1mZFQjIRDFfNhYeFBOFgfaoQ7R05i_I8haNNhcX"
        "qtqqFO_eX8fMfSGV4IWE8IBcy1v6JaLe-aDj1ceuSQ0uNqj8FNThw3PPQmC-N7RLg2PPvnkEW8"
        "T1Rt_bDVv3FBWAuHAWTsFCQB4nrBKcUkeKHD2Bsoa5BnH4KAqIPBpR0BG344aWzaL6HJdVbSsG"
        "Cb-7GDlZLRqLX-TbDgqdLdRHk1UKEy0PXpVGOI2CrTkYWztMWlFA8UktLarSPA=w1920-h943?"
        "auditContext=prefetch",
        "color": 0xB72476,
        "info": {
            "spreadsheetId": "1QSCRXKtiwoMTLV8knHC_o4NwV3UZM6ZvL-l9ZCPxoRM",
            "range": "Official Local Version!A2:E",
            "columns": InfoColumns.SSL.value,
            "replaceGrid": {
                "sheetId": 0,
                "startRowIndex": 1,
                "startColumnIndex": 1,
                "endColumnIndex": 2,
            },
        },
        "emblem": {
            "spreadsheetId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
            "range": "KD!A1:B",
            "columns": EMBLEM_COLUMNS,
            "replaceGrid": {
                "sheetId": 1200216146,
                "startRowIndex": 0,
                "startColumnIndex": 0,
                "endColumnIndex": 1,
            },
        },
        "pinChannelIds": {},
        "pinRoles": {},
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["KST"],
        "assetScheme": AssetScheme.JSON_URL,
    },
    "ATZ": {
        "name": "SUPERSTAR ATEEZ",
        "color": 0xDB811C,
        "info": {
            "spreadsheetId": "1ZRfm1D2sxV183umOvK4hdWUXIVWvd-Gc8nmRbnsmajY",
            "replaceGrid": {},
            "range": "Info!A2:G",
            "columns": InfoColumns.SHARED.value,
        },
        "bonus": {
            "spreadsheetId": "1ZRfm1D2sxV183umOvK4hdWUXIVWvd-Gc8nmRbnsmajY",
            "range": "Info!A2:J",
            "columns": BONUS_COLUMNS,
            "replaceGrid": {
                "sheetId": 0,
                "startRowIndex": 1,
                "startColumnIndex": 2,
                "endColumnIndex": 3,
            },
        },
        "ping": {
            "spreadsheetId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
            "range": "ATEEZ!C1:D",
            "columns": PING_COLUMNS,
            "replaceGrid": {
                "sheetId": 1373177550,
                "startRowIndex": 0,
                "startColumnIndex": 3,
                "endColumnIndex": 4,
            },
        },
        "emblem": {
            "spreadsheetId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
            "range": "ATEEZ!A1:B",
            "columns": EMBLEM_COLUMNS,
            "replaceGrid": {},
        },
        "pinChannelIds": {},
        "pinRoles": {},
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["KST"],
        "lookupQuery": "id=1571479814&country=kr",
        "manifestUrl": (
            "https://superstar-ateez.s3.amazonaws.com"
            "/version/real/manifest/{version}.txt"
        ),
        "assetScheme": AssetScheme.BINARY_CATALOG,
        "catalogUrl": (
            "http://d3kmsky8b54x07.cloudfront.net/assets"
            "/LIVE/iOS/catalog_{version}.bin"
        ),
        "authorization": "QWVob3JZcmxGanJ2dmRtTXY4S0w6SVJLR0lqTlRyRw==",
        "target_audience": "832096356756-6nust6ofm2hfoima94nd93uakqq44ev8",
    },
    "SC": {
        "name": "SUPERSTAR STAYC",
        "color": 0x210630,
        "info": {
            "spreadsheetId": "1zEBkb3oAqP_VkilWfJt6x0nfcrweVn7Ray--wNHqxjg",
            "replaceGrid": {},
            "range": "Info!A2:G",
            "columns": InfoColumns.SHARED.value,
        },
        "bonus": {
            "spreadsheetId": "1zEBkb3oAqP_VkilWfJt6x0nfcrweVn7Ray--wNHqxjg",
            "range": "Info!A2:J",
            "columns": BONUS_COLUMNS,
            "replaceGrid": {
                "sheetId": 0,
                "startRowIndex": 1,
                "startColumnIndex": 2,
                "endColumnIndex": 3,
            },
        },
        "ping": {
            "spreadsheetId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
            "range": "STAYC!C1:D",
            "columns": PING_COLUMNS,
            "replaceGrid": {
                "sheetId": 1795572100,
                "startRowIndex": 0,
                "startColumnIndex": 3,
                "endColumnIndex": 4,
            },
        },
        "emblem": {
            "spreadsheetId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
            "range": "STAYC!A1:B",
            "columns": EMBLEM_COLUMNS,
            "replaceGrid": {},
        },
        "pinChannelIds": {},
        "pinRoles": {},
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["KST"],
        "lookupQuery": "id=6446679596&country=kr",
        "manifestUrl": (
            "https://superstar-stayc.s3.amazonaws.com"
            "/version/real/manifest/{version}.txt"
        ),
        "assetScheme": AssetScheme.BINARY_CATALOG,
        "catalogUrl": (
            "https://d4ybtwjh1nw39.cloudfront.net/assets"
            "/LIVE/iOS/catalog_{version}.bin"
        ),
        "authorization": "WW5yI0VCPmlKM182fG5qXllrMzQ6THpULVQ3UF9dfg==",
        "target_audience": "154091709836-q1sk7hq02vi16f3v0q88uvuf6op5lenv",
    },
    "W1": {
        "name": "SUPERSTAR WAKEONE",
        "color": 0x4E25D1,
        "info": {
            "spreadsheetId": "1HHBluEEcWmZMHjq3WlLbS9TeLfPktQ3WrfxpcgReWF0",
            "replaceGrid": {
                "sheetId": 0,
                "startRowIndex": 1,
                "startColumnIndex": 1,
                "endColumnIndex": 2,
            },
            "range": "Songs (Note Count)!A2:D",
            "columns": InfoColumns.NO_SSL.value,
        },
        "emblem": {
            "spreadsheetId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
            "range": "W1!A1:B",
            "columns": EMBLEM_COLUMNS,
            "replaceGrid": {
                "sheetId": 1164880075,
                "startRowIndex": 0,
                "startColumnIndex": 0,
                "endColumnIndex": 1,
            },
        },
        "pinChannelIds": {},
        "pinRoles": {},
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["KST"],
        "lookupQuery": "id=6523424185&country=kr",
        "manifestUrl": (
            "https://superstar-wakeone.s3.amazonaws.com"
            "/version/real/manifest/{version}.txt"
        ),
        "assetScheme": AssetScheme.JSON_CATALOG,
        "catalogUrl": (
            "https://d189x7hw581nsg.cloudfront.net/assets/iOS/catalog_{version}.json"
        ),
        "target_audience": "259379396797-tfc19vpi39fosa2sic420po6l67p9ltu",
    },
    "SMTOWN": {
        "name": "SUPERSTAR SMTOWN (JP/TW)",
        "color": 0xE10989,
        "info": {
            "spreadsheetId": "1kC38CLFd6xkDXD9qLHgnnv3s3jmM_4vf4RLsWuXs9NU",
            "replaceGrid": {
                "sheetId": 0,
                "startRowIndex": 1,
                "startColumnIndex": 1,
                "endColumnIndex": 2,
            },
            "range": "Songs!A2:E",
            "columns": InfoColumns.SSL.value,
        },
        "bonus": {
            "spreadsheetId": "1kC38CLFd6xkDXD9qLHgnnv3s3jmM_4vf4RLsWuXs9NU",
            "range": "Bonuses!A2:J",
            "columns": BONUS_COLUMNS,
            "replaceGrid": {
                "sheetId": 1118940800,
                "startRowIndex": 1,
                "startColumnIndex": 2,
                "endColumnIndex": 3,
            },
        },
        "ping": {
            "spreadsheetId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
            "range": "SMTOWN!C1:D",
            "columns": PING_COLUMNS,
            "replaceGrid": {
                "sheetId": 755434019,
                "startRowIndex": 0,
                "startColumnIndex": 3,
                "endColumnIndex": 4,
            },
        },
        "emblem": {
            "spreadsheetId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
            "range": "SMTOWN!A1:B",
            "columns": EMBLEM_COLUMNS,
            "replaceGrid": {},
        },
        "pinChannelIds": {
            SSRG_GUILD: 481907573948153857,
            TEST_GUILD: 1343840449357418516,
        },
        "pinRoles": {},
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["JST"],
        "lookupQuery": "id=1216136006&country=jp",
        "manifestUrl": (
            "https://superstar-smtown-real.s3.amazonaws.com/version/{version}.txt"
        ),
        "assetScheme": AssetScheme.DIRECT_URL,
        "target_audience": "28835016655-choauh766oss3ht8ddqiamavvtfm05ur",
    },
    "JYPNATION": {
        "name": "SUPERSTAR JYPNATION (JP)",
        "color": 0x2377E4,
        "info": {
            "spreadsheetId": "1eVjwi0GudyMixnZtam8TeupRd3DQ6mheyRKp2lDA6qw",
            "replaceGrid": {
                "sheetId": 1514100857,
                "startRowIndex": 1,
                "startColumnIndex": 1,
                "endColumnIndex": 2,
            },
            "range": "Songs!A2:F",
            "columns": InfoColumns.SSL_WITH_SKILLS.value,
        },
        "bonus": {
            "spreadsheetId": "1eVjwi0GudyMixnZtam8TeupRd3DQ6mheyRKp2lDA6qw",
            "range": "Bonuses!A2:J",
            "columns": BONUS_COLUMNS,
            "replaceGrid": {
                "sheetId": 1285084831,
                "startRowIndex": 1,
                "startColumnIndex": 2,
                "endColumnIndex": 3,
            },
        },
        "ping": {
            "spreadsheetId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
            "range": "JYPNATION!C1:D",
            "columns": PING_COLUMNS,
            "replaceGrid": {
                "sheetId": 735198271,
                "startRowIndex": 0,
                "startColumnIndex": 3,
                "endColumnIndex": 4,
            },
        },
        "emblem": {
            "spreadsheetId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
            "range": "JYPNATION!A1:B",
            "columns": EMBLEM_COLUMNS,
            "replaceGrid": {},
        },
        "pinChannelIds": {
            SSRG_GUILD: 951350075190313010,
            TEST_GUILD: 1335936325685084242,
        },
        "pinRoles": {},
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["JST"],
        "lookupQuery": "id=1569554295&country=jp",
        "manifestUrl": (
            "https://superstar-jyp-jp-real.s3.amazonaws.com"
            "/version/manifest/{version}.txt"
        ),
        "assetScheme": AssetScheme.JSON_URL,
        "target_audience": "776124120237-r7q2lcrob52mp0asch12hbmkd52elej5",
    },
    "LP": {
        "name": "SUPERSTAR LAPONE",
        "color": 0xEAA715,
        "info": {
            "spreadsheetId": "1Ng57BGCDj025bxwCBbQulYFhRjS5runy5HnbStY_xSw",
            "replaceGrid": {
                "sheetId": 0,
                "startRowIndex": 1,
                "startColumnIndex": 1,
                "endColumnIndex": 2,
            },
            "range": "Songs!A2:F",
            "columns": InfoColumns.SSL_WITH_SKILLS.value,
        },
        "bonus": {
            "spreadsheetId": "1Ng57BGCDj025bxwCBbQulYFhRjS5runy5HnbStY_xSw",
            "range": "Bonuses!A2:J",
            "columns": BONUS_COLUMNS,
            "replaceGrid": {
                "sheetId": 126522384,
                "startRowIndex": 1,
                "startColumnIndex": 2,
                "endColumnIndex": 3,
            },
        },
        "ping": {
            "spreadsheetId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
            "range": "LAPONE!C1:D",
            "columns": PING_COLUMNS,
            "replaceGrid": {
                "sheetId": 0,
                "startRowIndex": 0,
                "startColumnIndex": 3,
                "endColumnIndex": 4,
            },
        },
        "emblem": {
            "spreadsheetId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
            "range": "LAPONE!A1:B",
            "columns": EMBLEM_COLUMNS,
            "replaceGrid": {},
        },
        "pinChannelIds": {
            SSRG_GUILD: 1039132737979813908,
            TEST_GUILD: 1340868523957813348,
        },
        "pinRoles": {},
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["JST"],
        "lookupQuery": "id=1642691486&country=jp",
        "manifestUrl": (
            "https://superstar-lapone-jp-real.s3.amazonaws.com"
            "/version/manifest/{version}.txt"
        ),
        "assetScheme": AssetScheme.JSON_URL,
        "target_audience": "668693032380-fmhat079lhao0o335ov5uk4jkl6kget6",
    },
    "EB": {
        "name": "SUPERSTAR EBiDAN",
        "color": 0xC71D1B,
        "info": {
            "spreadsheetId": "1uwLl0MQM895xI4iBmdP-eVVn7HKOBisFaQCCjzJL4GQ",
            "replaceGrid": {},
            "range": "Songs!A2:E",
            "columns": InfoColumns.NO_SSL.value,
        },
        "bonus": {
            "spreadsheetId": "1uwLl0MQM895xI4iBmdP-eVVn7HKOBisFaQCCjzJL4GQ",
            "range": "Bonuses!A2:J",
            "columns": BONUS_COLUMNS,
            "replaceGrid": {
                "sheetId": 1685871960,
                "startRowIndex": 1,
                "startColumnIndex": 2,
                "endColumnIndex": 3,
            },
        },
        "ping": {
            "spreadsheetId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
            "range": "EBiDAN!C1:D",
            "columns": PING_COLUMNS,
            "replaceGrid": {
                "sheetId": 1872493199,
                "startRowIndex": 0,
                "startColumnIndex": 3,
                "endColumnIndex": 4,
            },
        },
        "emblem": {
            "spreadsheetId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
            "range": "EBiDAN!A1:B",
            "columns": EMBLEM_COLUMNS,
            "replaceGrid": {},
        },
        "pinChannelIds": {},
        "pinRoles": {},
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["JST"],
        "lookupQuery": "id=6450412255&country=jp",
        "manifestUrl": (
            "https://superstar-ebidan-jp-real.s3.amazonaws.com"
            "/version/manifest/{version}.txt"
        ),
        "assetScheme": AssetScheme.JSON_URL,
        "target_audience": "1006848262784-luosgb8o1hrjvbu6v8mjgh35b5oiimli",
    },
    "PH": {
        "name": "SuperStar Philippines",
        "color": 0x04102D,
        "info": {
            "spreadsheetId": "1Fz71pl3YCUIbCRcZRuKBjsDT4JEW0m9Uoj8wyJhUMOc",
            "replaceGrid": {},
            "range": "Songs!A2:E",
            "columns": InfoColumns.NO_SSL.value,
        },
        "bonus": {
            "spreadsheetId": "1Fz71pl3YCUIbCRcZRuKBjsDT4JEW0m9Uoj8wyJhUMOc",
            "range": "Bonuses!A2:J",
            "columns": BONUS_COLUMNS,
            "replaceGrid": {
                "sheetId": 0,
                "startRowIndex": 1,
                "startColumnIndex": 2,
                "endColumnIndex": 3,
            },
        },
        "ping": {
            "spreadsheetId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
            "range": "Philippines!C1:D",
            "columns": PING_COLUMNS,
            "replaceGrid": {
                "sheetId": 564410793,
                "startRowIndex": 0,
                "startColumnIndex": 3,
                "endColumnIndex": 4,
            },
        },
        "emblem": {
            "spreadsheetId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
            "range": "Philippines!A1:B",
            "columns": EMBLEM_COLUMNS,
            "replaceGrid": {},
        },
        "pinChannelIds": {},
        "pinRoles": {},
        "dateFormat": "%d-%m-%Y",
        "timezone": TIMEZONES["PHT"],
        "lookupQuery": "id=6451133069&country=us",
        "manifestUrl": (
            "https://superstar-philippines.s3.amazonaws.com"
            "/version/real/manifest/{version}.txt"
        ),
        "assetScheme": AssetScheme.JSON_URL,
        "authorization": "WWFeNnhxVldSJWFkVWp4Z3ViOFY6WmJRcy1uZ1YyQQ==",
        "target_audience": "234980834479-creie63p99odjttcv9pvifjelsuf983i",
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
