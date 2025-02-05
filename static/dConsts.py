from apiclient import discovery
from Cryptodome.Cipher import AES
from google.oauth2 import service_account

from static.dTypes import SSLD, BonusD

DISCORD_TOKEN = (
    "MTMzNTMwNzU4ODU5NzcxMDg2OA.GZsv8G.201CKGpn6AuCsHyiQfXfcpr2qQKzMnYomsC3z8"
)
TEST_GUILD = 540849436868214784
STATUS_CHANNEL = 1335315390732963952

OK_ROLE_OWNER = 973231666711634001
SSRG_ROLE_MOD = 1039013749597683742
SSRG_ROLE_SS = 439095346061377536

gCredentials = service_account.Credentials.from_service_account_file(
    filename="service_account.json",
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)
sheetService = discovery.build(
    serviceName="sheets", version="v4", credentials=gCredentials
).spreadsheets()

A_JSON_HEADERS = {
    "X-SuperStar-AES-IV": "PUIEOQYGNEFFFUAX",
    "X-SuperStar-Asset-Ignore": "true",
    "X-SuperStar-API-Version": "8",
}
A_JSON_BODY = (
    "/OBWvurTOUC41Z8AbFs6LbFZ6vZZSLpHL+SXK4yVJ4yT"
    "+FQDGqcb8Vy51zOBdtzgUYHWzeN0LAWE6Mll+Kpb3w=="
)
ssCrypt = AES.new("WnFKN1v_gUcgmUVZnjjjGXGwk557zBSO".encode("utf8"), AES.MODE_ECB)

TIMEZONES = {
    "KST": "Asia/Tokyo",
    "JST": "Asia/Tokyo",
    "PHT": "Asia/Manila",
    "ICT": "Asia/Bangkok",
}

SSLS: dict[str, SSLD] = {
    "JYP_JP": {
        "spreadsheetId": "1eVjwi0GudyMixnZtam8TeupRd3DQ6mheyRKp2lDA6qw",
        "spreadsheetRange": "Songs!A2:F",
        "spreadsheetColumns": [
            "song_id",
            "artist_name",
            "song_name",
            "duration",
            "image",
            "skills",
        ],
        "pinChannelId": 1335936325685084242,
        "timezone": TIMEZONES["JST"],
        "api": "https://ss-jyp-api-real.superstarjyp.jp",
    },
    "LP": {
        "spreadsheetId": "1Ng57BGCDj025bxwCBbQulYFhRjS5runy5HnbStY_xSw",
        "spreadsheetRange": "Songs!A2:F",
        "spreadsheetColumns": [
            "song_id",
            "artist_name",
            "song_name",
            "duration",
            "image",
            "skills",
        ],
        "pinChannelId": 1336210286289616917,
        "timezone": TIMEZONES["JST"],
        "api": "https://ss-lapone-api-real.superstarlapone.jp",
    },
}

BONUSES: dict[str, BonusD] = {
    "JYP_JP": {
        "name": "SUPERSTAR JYPNATION (JP)",
        "pingId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingRange": "JYPNATION!A1:B",
        "pingWrite": "JYPNATION!B",
        "pingColumns": ["artist_name", "users"],
        "bonusId": "1eVjwi0GudyMixnZtam8TeupRd3DQ6mheyRKp2lDA6qw",
        "bonusRange": "Bonuses!A2:J",
        "bonusColumns": [
            "song_id", "bonus_amount", "artist_name", "member_name", "album_name",
            "song_name", "duration", "bonus_date", "bonus_start", "bonus_end"
        ],
        "timezone": TIMEZONES["JST"],
    },
    "LP": {
        "name": "SUPERSTAR LAPONE",
        "pingId": "1GYcHiRvR_VZiH1w51ISgjbE63WUvMXH32bNZl3dWV_s",
        "pingRange": "LAPONE!A1:B",
        "pingWrite": "LAPONE!B",
        "pingColumns": ["artist_name", "users"],
        "bonusId": "1Ng57BGCDj025bxwCBbQulYFhRjS5runy5HnbStY_xSw",
        "bonusRange": "Bonuses!A2:J",
        "bonusColumns": [
            "song_id", "bonus_amount", "artist_name", "member_name", "album_name",
            "song_name", "duration", "bonus_date", "bonus_start", "bonus_end"
        ],
        "timezone": TIMEZONES["JST"],
    },
}
