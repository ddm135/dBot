from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from statics.types import GameDetails

TEST_GUILD = 540849436868214784
SSRG_GUILD = 360109303199432704
PINATA_TEST_CHANNEL = 1354222667384885329
STATUS_CHANNEL = 1335315390732963952
ME = 180925261531840512

MAX_RETRIES = 10
MAX_AUTOCOMPLETE = 25

BONUS_OFFSET = timedelta(days=1)
RESET_OFFSET = timedelta(hours=2)

AES_KEY = b"WnFKN1v_gUcgmUVZnjjjGXGwk557zBSO"
IV_LENGTH = 16

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
    "statics.types",
    "statics.consts",
    "statics.services",
    "statics.helpers",
)

EXTENSIONS = (
    "events.on_command_error",
    "events.on_message",
    "events.on_ready",
    "commands.administrative",
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
    "tasks.pinata",
    "commands.miscellaneous",
)

PING_DATA = Path("data/pings.json")
ROLE_DATA = Path("data/roles.json")
CREDENTIALS_DATA = Path("data/credentials.json")
LOCK = Path(".dBot")

GAMES: dict[str, "GameDetails"] = {
    "SM": {
        "name": "SUPERSTAR SM",
        "infoId": "1dX_5lWxenT7CDVXpgyScTHDiwazUZIO3441RaNpN55g",
        "infoRange": "Songs!A2:E",
        "infoColumns": (
            "song_id",
            "artist_name",
            "song_name",
            "search_term",
            "duration",
        ),
        "pingId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingRange": "SM!A1:D",
        "pingWrite": "SM!C",
        "pingColumns": ("artist_name", "emblem", "users"),
        "bonusId": "1dX_5lWxenT7CDVXpgyScTHDiwazUZIO3441RaNpN55g",
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
        "color": 0xEA04F0,
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
        "legacyUrlScheme": False,
    },
    "JYP": {
        "name": "SUPERSTAR JYP",
        "infoId": "1XgaSMje3TKa1bnekWzmpLRjr81QWoag_6w9SlzSwN0g",
        "infoRange": "Songs!A2:E",
        "infoColumns": (
            "song_id",
            "artist_name",
            "song_name",
            "search_term",
            "duration",
        ),
        "pingId": "",
        "pingRange": "JYP!A1:D",
        "pingWrite": "JYP!C",
        "pingColumns": ("artist_name", "emblem", "users"),
        "bonusId": "",
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
        "color": 0x4776FB,
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
        "legacyUrlScheme": False,
    },
    "SC": {
        "name": "SUPERSTAR STAYC",
        "infoId": "1zEBkb3oAqP_VkilWfJt6x0nfcrweVn7Ray--wNHqxjg",
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
        "pingId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingRange": "STAYC!A1:D",
        "pingWrite": "STAYC!C",
        "pingColumns": ("artist_name", "emblem", "users"),
        "bonusId": "1zEBkb3oAqP_VkilWfJt6x0nfcrweVn7Ray--wNHqxjg",
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
        "color": 0x3E0654,
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
        "legacyUrlScheme": False,
    },
    "WO": {
        "name": "SUPERSTAR WAKEONE",
        "infoId": "1HHBluEEcWmZMHjq3WlLbS9TeLfPktQ3WrfxpcgReWF0",
        "infoRange": "Songs (Note Count)!A2:D",
        "infoColumns": (
            "song_id",
            "artist_name",
            "song_name",
            "duration",
        ),
        "pingId": "",
        "pingRange": "",
        "pingWrite": "",
        "pingColumns": (),
        "bonusId": "",
        "bonusRange": "",
        "bonusColumns": (),
        "color": 0x4623CE,
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
        "legacyUrlScheme": False,
    },
    "SM_JP": {
        "name": "SUPERSTAR SMTOWN (JP/TW)",
        "infoId": "1kC38CLFd6xkDXD9qLHgnnv3s3jmM_4vf4RLsWuXs9NU",
        "infoRange": "Songs!A2:E",
        "infoColumns": (
            "song_id",
            "artist_name",
            "song_name",
            "search_term",
            "duration",
        ),
        "pingId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingRange": "SMTOWN!A1:D",
        "pingWrite": "SMTOWN!C",
        "pingColumns": ("artist_name", "emblem", "users"),
        "bonusId": "1kC38CLFd6xkDXD9qLHgnnv3s3jmM_4vf4RLsWuXs9NU",
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
        "color": 0xD60480,
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
        "legacyUrlScheme": False,
    },
    "JYP_JP": {
        "name": "SUPERSTAR JYPNATION (JP)",
        "infoId": "1eVjwi0GudyMixnZtam8TeupRd3DQ6mheyRKp2lDA6qw",
        "infoRange": "Songs!A2:F",
        "infoColumns": (
            "song_id",
            "artist_name",
            "song_name",
            "search_term",
            "duration",
            "skills",
        ),
        "pingId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingRange": "JYPNATION!A1:D",
        "pingWrite": "JYPNATION!C",
        "pingColumns": ("artist_name", "emblem", "users"),
        "bonusId": "1eVjwi0GudyMixnZtam8TeupRd3DQ6mheyRKp2lDA6qw",
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
        "color": 0x1A6DE1,
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
        "legacyUrlScheme": True,
    },
    "LP": {
        "name": "SUPERSTAR LAPONE",
        "infoId": "1Ng57BGCDj025bxwCBbQulYFhRjS5runy5HnbStY_xSw",
        "infoRange": "Songs!A2:F",
        "infoColumns": (
            "song_id",
            "artist_name",
            "song_name",
            "search_term",
            "duration",
            "skills",
        ),
        "pingId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingRange": "LAPONE!A1:D",
        "pingWrite": "LAPONE!C",
        "pingColumns": ("artist_name", "emblem", "users"),
        "bonusId": "1Ng57BGCDj025bxwCBbQulYFhRjS5runy5HnbStY_xSw",
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
        "color": 0xFF9700,
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
        "legacyUrlScheme": True,
    },
    "EB": {
        "name": "SUPERSTAR EBiDAN",
        "infoId": "",
        "infoRange": "",
        "infoColumns": (),
        "pingId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingRange": "EBiDAN!A1:D",
        "pingWrite": "EBiDAN!C",
        "pingColumns": ("artist_name", "emblem", "users"),
        "bonusId": "1uwLl0MQM895xI4iBmdP-eVVn7HKOBisFaQCCjzJL4GQ",
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
        "color": 0x960C19,
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
        "target_audience": "",
        "legacyUrlScheme": True,
    },
    "PH": {
        "name": "SuperStar Philippines",
        "infoId": "",
        "infoRange": "",
        "infoColumns": (),
        "pingId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingRange": "Philippines!A1:D",
        "pingWrite": "Philippines!C",
        "pingColumns": ("artist_name", "emblem", "users"),
        "bonusId": "1Fz71pl3YCUIbCRcZRuKBjsDT4JEW0m9Uoj8wyJhUMOc",
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
        "color": 0x071543,
        "pinChannelIds": {},
        "pinRoles": {},
        "dateFormat": "%d-%m-%Y",
        "timezone": TIMEZONES["PHT"],
        "manifest": (
            "https://superstar-philippines.s3.amazonaws.com"
            "/version/real/manifest/{version}.txt"
        ),
        "api": "https://ssph-api-https.dalcomsoft.net",
        "authorization": "",
        "target_audience": "",
        "legacyUrlScheme": True,
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

PINATA: dict[str, list[dict[str, int | str]]] = {
    # "0328": [
    #     # {"role": 427282007131947008, "from": "TWICE"},
    #     # {"role": 492037142718185473, "from": None},
    #     # {"role": 431680345184665600, "from": "EXO"},
    #     {"role": 1341036401483055147, "from": "ym"},
    #     {"role": 1341634094269988946, "from": ""},
    # ]
    "0331": [
        {"role": "End of service notice", "from": ""},
        {"role": "Notice", "from": "Refund"},
    ],
    "0401": [
        {"role": "End of service notice", "from": ""},
        {"role": "Notice", "from": "Refund"},
    ],
}
