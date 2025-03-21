from datetime import timedelta
from zoneinfo import ZoneInfo

from static.dTypes import GameDetails

TEST_GUILD = 540849436868214784
SSRG_GUILD = 360109303199432704
STATUS_CHANNEL = 1335315390732963952
MAX_AUTOCOMPLETE_RESULTS = 25

TEST_ROLE_OWNER = 973231666711634001
SSRG_ROLE_MOD = 1039013749597683742
SSRG_ROLE_SS = 439095346061377536

ROLE_STORAGE_CHANNEL = {
    TEST_GUILD: 1341379038882824192,
    SSRG_GUILD: 931718347190591498,
}

MAX_RETRIES = 10
ONE_DAY = timedelta(days=1)

AES_KEY = "WnFKN1v_gUcgmUVZnjjjGXGwk557zBSO"
AES_IV = "PUIEOQYGNEFFFUAX"
A_JSON_HEADERS = {
    "X-SuperStar-AES-IV": AES_IV,
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
    "CST": ZoneInfo("Asia/Taipei"),
    "PHT": ZoneInfo("Asia/Manila"),
}

EXTENSIONS = [
    "commands.administrative",
    "commands.memes",
    "app_commands.bonus",
    "app_commands.role",
    "app_commands.ssLeague",
    "tasks.clock",
    "tasks.info_sync",
    "tasks.role_sync",
    "tasks.notify_p8",
    "tasks.notify_p9",
]

GAMES: dict[str, GameDetails] = {
    "SM": {
        "name": "SUPERSTAR SM",
        "infoId": "1kC38CLFd6xkDXD9qLHgnnv3s3jmM_4vf4RLsWuXs9NU",
        "infoArtists": "Artists!A2:A",
        "infoSongs": "Songs!A2:F",
        "infoColumns": (
            "song_id",
            "artist_name",
            "song_name",
            "search_term",
            "duration",
            "image",
        ),
        "pingId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingRange": "SM!A1:D",
        "pingWrite": "SM!C",
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
        "color": 0xEA04F0,
        "pinChannelIds": {
            TEST_GUILD: 1336210286289616917,
            SSRG_GUILD: 401291379810107394,
        },
        "pinRoles": {
            TEST_GUILD: 1350860245487845570,
            SSRG_GUILD: 420428449325252608,
        },
        # "api": "https://smtown-api-https.dalcomsoft.net",
        "api": "http://ss-sm-api-real.superstarsmtown.jp",
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["KST"],
        "resetOffset": timedelta(hours=2),
    },
    "SM_JP": {
        "name": "SUPERSTAR SMTOWN (JP/TW)",
        "infoId": "1kC38CLFd6xkDXD9qLHgnnv3s3jmM_4vf4RLsWuXs9NU",
        "infoArtists": "Artists!A2:A",
        "infoSongs": "Songs!A2:F",
        "infoColumns": (
            "song_id",
            "artist_name",
            "song_name",
            "search_term",
            "duration",
            "image",
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
            TEST_GUILD: 1343840449357418516,
            SSRG_GUILD: 481907573948153857,
        },
        "pinRoles": None,
        "api": "http://ss-sm-api-real.superstarsmtown.jp",
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["JST"],
        "resetOffset": timedelta(hours=2),
    },
    # "G": {
    #     "name": "SUPERSTAR GFRIEND",
    #     "infoId": "",
    #     "infoArtists": "",
    #     "infoSongs": "",
    #     "infoColumns": (),
    #     "pingId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
    #     "pingRange": "GFRIEND!A1:D",
    #     "pingWrite": "GFRIEND!C",
    #     "pingColumns": ("artist_name", "emblem", "users"),
    #     "bonusId": "1V1f3xp24R5AA7yDP0OAZLu5ZVPiMZKE31EkDkoIfhJY",
    #     "bonusRange": "Bonuses!A2:J",
    #     "bonusColumns": (
    #         "song_id",
    #         "bonus_amount",
    #         "artist_name",
    #         "member_name",
    #         "album_name",
    #         "song_name",
    #         "duration",
    #         "bonus_date",
    #         "bonus_start",
    #         "bonus_end",
    #     ),
    #     "color": 0x00ABC0,
    #     "pinChannelIds": None,
    #     "pinRoles": None,
    #     "api": "https://ssg-api-https.dalcomsoft.net/api",
    #     "dateFormat": "%Y-%m-%d",
    #     "timezone": TIMEZONES["KST"],
    #     "resetOffset": timedelta(hours=2),
    # },
    "JYP_JP": {
        "name": "SUPERSTAR JYPNATION (JP)",
        "infoId": "1eVjwi0GudyMixnZtam8TeupRd3DQ6mheyRKp2lDA6qw",
        "infoArtists": "Artists!A2:A",
        "infoSongs": "Songs!A2:G",
        "infoColumns": (
            "song_id",
            "artist_name",
            "song_name",
            "search_term",
            "duration",
            "image",
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
            TEST_GUILD: 1335936325685084242,
            SSRG_GUILD: 951350075190313010,
        },
        "pinRoles": None,
        "api": "https://ss-jyp-api-real.superstarjyp.jp",
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["JST"],
        "resetOffset": timedelta(hours=2),
    },
    "LP": {
        "name": "SUPERSTAR LAPONE",
        "infoId": "1Ng57BGCDj025bxwCBbQulYFhRjS5runy5HnbStY_xSw",
        "infoArtists": "Artists!A2:A",
        "infoSongs": "Songs!A2:G",
        "infoColumns": (
            "song_id",
            "artist_name",
            "song_name",
            "search_term",
            "duration",
            "image",
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
            TEST_GUILD: 1340868523957813348,
            SSRG_GUILD: 1039132737979813908,
        },
        "pinRoles": None,
        "api": "https://ss-lapone-api-real.superstarlapone.jp",
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["JST"],
        "resetOffset": timedelta(hours=2),
    },
    "EB": {
        "name": "SUPERSTAR EBiDAN",
        "infoId": "",
        "infoArtists": "",
        "infoSongs": "",
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
        "pinChannelIds": None,
        "pinRoles": None,
        "api": "https://ss-ebidan-api-real.superstarebidan.jp",
        "dateFormat": "%Y-%m-%d",
        "timezone": TIMEZONES["JST"],
        "resetOffset": timedelta(hours=2),
    },
    "PH": {
        "name": "SuperStar Philippines",
        "infoId": "",
        "infoArtists": "",
        "infoSongs": "",
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
        "pinChannelIds": None,
        "pinRoles": None,
        "api": "https://ssph-api-https.dalcomsoft.net",
        "dateFormat": "%d-%m-%Y",
        "timezone": TIMEZONES["PHT"],
        "resetOffset": timedelta(hours=2),
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
