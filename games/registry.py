"""The games the bot knows, one :class:`Game` each, keyed by its short name."""

import re
from collections.abc import Mapping
from datetime import date
from types import MappingProxyType
from zoneinfo import ZoneInfo

from discord_ids import SSRG_GUILD, TEST_GUILD
from games.data.schema import ENGLISH_FIRST, JAPANESE_FIRST, KOREAN_FIRST
from games.models import (
    AppStoreLookup,
    CatalogPatterns,
    ForwardConfig,
    Game,
    GrpcConfig,
    PinTarget,
    StringsConfig,
)

KST = ZoneInfo("Asia/Seoul")
JST = ZoneInfo("Asia/Tokyo")
PHT = ZoneInfo("Asia/Manila")

NORMAL_BASE_SCORE = 6_358_000
PRISM_BASE_SCORE = 6_909_000

_KANGDANIEL_ICON_URL = "https://lh3.googleusercontent.com/fife/ALs6j_F5p1r_gQeZEflvr7ITq6WPNV3baQB9c3WRnoXMU1tVyBWdls2WF17Fi-gRYlKERFF-RYmbP_tHqoWUdw-Qe8UQcl120gropBajFxrOWfJDrP-6MzB_-CQpMIQMYEro_xafihKHHUS4P3nOhPaQBM1flRiQD0Rg5dw4E0fUiXNUy7chCIzPiTh7VZLF6zGlrB-uz9fMYKg_35JS_yCQv_ysZwBjmWtDmVI6Gh3sjc0EPppijCsFAXlKdLAZLm0blHtfqmxhafKVrhmq0XyHCjQ04pxw8CGOMNNTpSvd9MYQELPiPTZt2QykEj21hJ9rYzWCpyHVA3meJpeKQS7OZllbDgfh3nHlylTeq6LrWiZbaatznSbXPhEKYx2gSztUdPccsPTYr9X3c3J5HjHIhtsovYH-4LhIhO1P767BQGtflPzzZMIRvG54ARL_2THgxphjJYxILk-etoFAe35SW18w49gAporBqvcBodObPURcrB8C6jyFWZLhMCERu2jjdgDEXnYZ2n5iSy6Q04cPYYVOjIX9EDrkg18kg0vvMnkQ2VcK3kUbdqcEbi5x_-T13Uw8GDWcCyDuEe09Vmw9tMxL5N7wVyOyx9qXEYvpAp9LRS1mxRveGt-LG-pNH0EEMdGOgcMoVdEBMzWi0gJ2Zc9H82J9PXD7Zd68xZPUhiOuVEBwMbVOwKPNsR3nLAgVtUMhMNqOBWRpdWRHLd7kRo08MltORdIa4QWWJeWDHsqGmK3vb_UewDE8t2iHCCK3cPKQ5L2m9vZ1pQCln5upBHilk7-L6Oj-bpTJRDIMV78BKsSAaFyXlE_HOE28KFf4Qv7frYvm1dI6ptXc9J6dv_P-s_M6dGawGT7KY6u4rDcrhg4taiWNWTH-5qbNh6-xWpepeQ0wbMtuYPyVZV_i_BVNrMJAPl8P9UjVoEWweAlPX5uUV5nyCymDSOGU5-m1mpQi-bjSlkuFCg_0E6uy_SAD_P0SVbwFFMzNLPKps-iV0RTq-PmPHgT1OJGZ3ENQgiMa7hWW5Ef4Lv9GAfBeX7-syMJtoTO3-aboiGkauVWidEtuJItsdzqW5_4ve4kNt4SuH97EheoX2fmNcX6Z_fDILAbNkPvY3ktc8-MoqMk8zup4oFlcDK1CQwsgkiMStwPiuCkRJccPPGfyAS1za2RKsWzsU5s67L_eDE_bpSzCkMs23BXedgjC2U_HXqOd-QPRho6c5E_-Iym46uGcAYG0ZvozetFlmnmY3VT5HjyJ34WTDKL4B4sOF2Eni2WkTKgaBAqfoXhVIO82D1fGdn_XPKPK2EOQKtAUnEzFQyTtYTFs06BeNzcn6-IQsA5Fx8kbxsZnupeo9T8IQjJ2QOxVUPgZEdpKQIi9ivV-aURpHC07F9F62kjr-ukyKwMmsOBnbNZ2ofvLyFmV33ZwrqnxzL16QskEWfWBLKx6IzxweJormHpnp1mZFQjIRDFfNhYeFBOFgfaoQ7R05i_I8haNNhcXqtqqFO_eX8fMfSGV4IWE8IBcy1v6JaLe-aDj1ceuSQ0uNqj8FNThw3PPQmC-N7RLg2PPvnkEW8T1Rt_bDVv3FBWAuHAWTsFCQB4nrBKcUkeKHD2Bsoa5BnH4KAqIPBpR0BG344aWzaL6HJdVbSsGCb-7GDlZLRqLX-TbDgqdLdRHk1UKEy0PXpVGOI2CrTkYWztMWlFA8UktLarSPA=w1920-h943?auditContext=prefetch"

_GAMES: tuple[Game, ...] = (
    Game(
        key="SM",
        name="SUPERSTAR SM",
        languages=KOREAN_FIRST,
        color=0xE204DD,
        timezone=KST,
        date_format="%Y-%m-%d",
        package_name="kr.co.dalcomsoft.superstar.a",
        version_floor="3.31.4",
        manifest_url="https://super-star.s3.amazonaws.com/version/live/manifest/{version}.txt",
        has_bonuses=True,
        base_score=NORMAL_BASE_SCORE,
        pins={
            SSRG_GUILD: PinTarget(401291379810107394, 420428449325252608),
            TEST_GUILD: PinTarget(1336210286289616917, 1350860245487845570),
        },
        forward=ForwardConfig(
            maintenance_channel_id=1413706777375014943,
            targets={
                SSRG_GUILD: 401291379810107394,
                TEST_GUILD: 1336210286289616917,
            },
        ),
        app_store=AppStoreLookup(890937532, "kr"),
        catalog_url="https://ssm-cdn.dalcomsoft.net/assets/LIVE/Android/{addressables}/catalog_{version}.bin",
        dalcom_authorization="SFFINkh6ckdwRkZiRmlYeis1Mi86U1cwU0JxdWg1dw==",
        google_audience="864447301209-h0hsb0denh03td7sgoelh5lmdvv79f9h",
    ),
    Game(
        key="JYP",
        name="SUPERSTAR JYP",
        languages=KOREAN_FIRST,
        color=0x4977FB,
        timezone=KST,
        date_format="%Y-%m-%d",
        package_name="com.dalcomsoft.ss.jyp",
        version_floor="3.31.4",
        manifest_url="https://superstar-jyp-resource.s3.amazonaws.com/version/live/manifest/{version}.txt",
        has_bonuses=True,
        base_score=NORMAL_BASE_SCORE,
        pins={
            SSRG_GUILD: PinTarget(360109303199432705, 420428238171668480),
            TEST_GUILD: PinTarget(1354222667384885329),
        },
        forward=ForwardConfig(
            maintenance_channel_id=1413706832953872414,
            targets={
                SSRG_GUILD: 360109303199432705,
                TEST_GUILD: 1354222667384885329,
            },
        ),
        app_store=AppStoreLookup(1086866467, "kr"),
        catalog_url="https://ssj-cdn.dalcomsoft.net/live/assets/LIVE/Android/{addressables}/catalog_{version}.bin",
        dalcom_authorization="MHhYTEhMQnV1aGpqY3ZRd1JHbUY6SlE0VFZZaVhXYw==",
        google_audience="506321732908-4u8t2uk3888gm8087i7lcpi97ff6ld4a",
    ),
    Game(
        key="SS",
        name="SUPERSTAR STARSHIP",
        languages=KOREAN_FIRST,
        color=0x484E8A,
        timezone=KST,
        date_format="%Y-%m-%d",
        package_name="com.dalcomsoft.sss",
        version_floor="3.31.4",
        manifest_url="https://superstar-starship.s3.amazonaws.com/version/live/manifest/{version}.txt",
        has_bonuses=True,
        base_score=NORMAL_BASE_SCORE,
        forward=ForwardConfig(
            maintenance_channel_id=1413706721494438039,
            targets={
                SSRG_GUILD: 629497534804525066,
                TEST_GUILD: 1413706247185633412,
            },
        ),
        app_store=AppStoreLookup(1480181152, "kr"),
        catalog_url="https://sss-cdn.dalcomsoft.net/assets/LIVE/Android/{addressables}/catalog_{version}.bin",
        dalcom_authorization="bnZQb1RweVg4WVlyUlZERE85Zkc6WVBrQklrNFdhcQ==",
        google_audience="42043845970-4hm4teclds9q4pji2on6f8o35n4ji6ac",
    ),
    Game(
        key="KD",
        name="SuperStar KANGDANIEL",
        languages=KOREAN_FIRST,
        color=0xB72476,
        timezone=KST,
        date_format="%Y-%m-%d",
        package_name="com.dalcomsoft.kangdaniel",
        version_floor="4.0.0",
        manifest_url="https://superstar-kangdaniel.s3.amazonaws.com/version/real/manifest/{version}.txt",
        icon_url=_KANGDANIEL_ICON_URL,
    ),
    Game(
        key="ATZ",
        name="SUPERSTAR ATEEZ",
        languages=KOREAN_FIRST,
        color=0xDB811C,
        timezone=KST,
        date_format="%Y-%m-%d",
        package_name="com.dalcomsoft.ssat",
        version_floor="3.31.4",
        manifest_url="https://superstar-ateez.s3.amazonaws.com/version/live/manifest/{version}.txt",
        has_bonuses=True,
        base_score=PRISM_BASE_SCORE,
        forward=ForwardConfig(
            maintenance_channel_id=1413706800049688647,
            targets={
                SSRG_GUILD: 872044312731484200,
                TEST_GUILD: 1413706348469682187,
            },
        ),
        app_store=AppStoreLookup(1571479814, "kr"),
        catalog_url="https://ssat-cdn.dalcomsoft.net/assets/LIVE/Android/{addressables}/catalog_{version}.bin",
        dalcom_authorization="QWVob3JZcmxGanJ2dmRtTXY4S0w6SVJLR0lqTlRyRw==",
        google_audience="832096356756-6nust6ofm2hfoima94nd93uakqq44ev8",
    ),
    Game(
        key="SC",
        name="SUPERSTAR HIGHUP",
        languages=KOREAN_FIRST,
        color=0x210630,
        timezone=KST,
        date_format="%Y-%m-%d",
        package_name="com.dalcomsoft.stayc",
        version_floor="3.31.4",
        manifest_url="https://superstar-stayc.s3.amazonaws.com/version/live/manifest/{version}.txt",
        has_bonuses=True,
        base_score=PRISM_BASE_SCORE,
        forward=ForwardConfig(
            maintenance_channel_id=1413706850389725244,
            scheduled_channel_id=1418938625348997200,
            targets={
                SSRG_GUILD: 1104332747008389231,
                TEST_GUILD: 1413706402790379520,
            },
        ),
        app_store=AppStoreLookup(6446679596, "kr"),
        catalog_url="https://sssc-cdn.dalcomsoft.net/assets/LIVE/Android/{addressables}/catalog_{version}.bin",
        dalcom_authorization="WW5yI0VCPmlKM182fG5qXllrMzQ6THpULVQ3UF9dfg==",
        google_audience="154091709836-q1sk7hq02vi16f3v0q88uvuf6op5lenv",
    ),
    Game(
        key="W1",
        name="SUPERSTAR WAKEONE",
        languages=KOREAN_FIRST,
        color=0x5400FF,
        timezone=KST,
        date_format="%Y-%m-%d",
        package_name="com.dalcomsoft.sswo",
        version_floor="3.31.4",
        manifest_url="https://superstar-wakeone.s3.amazonaws.com/version/live/manifest/{version}.txt",
        forward=ForwardConfig(
            maintenance_channel_id=1413706817548189807,
            targets={
                SSRG_GUILD: 1291640600080289803,
                TEST_GUILD: 1413706513561681930,
            },
        ),
        first_season=date(2024, 12, 2),
        app_store=AppStoreLookup(6523424185, "kr"),
        catalog_url="https://sswo-cdn.dalcomsoft.net/assets/LIVE/Android/{addressables}/catalog_{version}.bin",
        google_audience="259379396797-tfc19vpi39fosa2sic420po6l67p9ltu",
    ),
    Game(
        key="BL",
        name="SUPERSTAR THEBLACKLABEL",
        languages=KOREAN_FIRST,
        album_decks=True,
        album_image_key="Image_Album_{code}",
        strings=StringsConfig(
            "ItemName",
            ("ko", "en", "ja"),
            "Album_{code}",
            "Group_{code}",
            "Music_{code}",
        ),
        color=0x000000,
        timezone=KST,
        date_format="%Y-%m-%d",
        package_name="com.dalcomsoft.ssbl",
        version_floor="1.0.9",
        manifest_url="https://superstar-theblacklabel.s3.amazonaws.com/version/prod/manifest/{version}.txt",
        forward=ForwardConfig(
            maintenance_channel_id=1489895419952758835,
            targets={
                SSRG_GUILD: 1452684579092828292,
            },
        ),
        app_store=AppStoreLookup(6738368827, "kr"),
        catalog_url="https://ssbl-cdn.dalcomsoft.net/live/assets/LIVE/Android/{addressables}/catalog_{version}.bin",
        catalog_patterns=CatalogPatterns(
            sound=re.compile("Audio_Music_(\\d+)"),
            seq=re.compile("bytes_notes_(\\d+)_([a-z]+)"),
            border=re.compile("Image_ThemeType_(\\d+)_R_Large"),
        ),
        grpc=GrpcConfig(
            target="ssbl.dalcomsoft.net:443", cdn_url="https://ssbl-cdn.dalcomsoft.net"
        ),
    ),
    Game(
        key="SMTOWN",
        name="SUPERSTAR SMTOWN (JP/TW)",
        languages=JAPANESE_FIRST,
        color=0xE10989,
        timezone=JST,
        date_format="%Y-%m-%d",
        package_name="jp.co.ponos.superstarsmtown",
        version_floor="3.6.6",
        manifest_url="https://superstar-smtown-real.s3.amazonaws.com/version/{version}.txt",
        has_bonuses=True,
        base_score=NORMAL_BASE_SCORE,
        pins={
            SSRG_GUILD: PinTarget(481907573948153857),
            TEST_GUILD: PinTarget(1343840449357418516),
        },
        app_store=AppStoreLookup(1216136006, "jp"),
        google_audience="28835016655-choauh766oss3ht8ddqiamavvtfm05ur",
    ),
    Game(
        key="JYPNATION",
        name="SUPERSTAR JYPNATION (JP)",
        languages=JAPANESE_FIRST,
        color=0x2377E4,
        timezone=JST,
        date_format="%Y-%m-%d",
        package_name="jp.co.dalcomsoft.superstarjypnation",
        version_floor="3.7.1",
        manifest_url="https://superstar-jyp-jp-real.s3.amazonaws.com/version/manifest/{version}.txt",
        has_bonuses=True,
        pins={
            SSRG_GUILD: PinTarget(951350075190313010),
            TEST_GUILD: PinTarget(1335936325685084242),
        },
        app_store=AppStoreLookup(1569554295, "jp"),
        google_audience="776124120237-r7q2lcrob52mp0asch12hbmkd52elej5",
    ),
    Game(
        key="EB",
        name="SUPERSTAR EBiDAN",
        languages=JAPANESE_FIRST,
        color=0xC71D1B,
        timezone=JST,
        date_format="%Y-%m-%d",
        package_name="jp.co.dalcomsoft.superstarebidan",
        version_floor="1.6.0",
        manifest_url="https://superstar-ebidan-jp-real.s3.amazonaws.com/version/manifest/{version}.txt",
        has_bonuses=True,
        app_store=AppStoreLookup(6450412255, "jp"),
        google_audience="1006848262784-luosgb8o1hrjvbu6v8mjgh35b5oiimli",
    ),
    Game(
        key="LDH",
        name="SUPERSTAR LDH",
        languages=JAPANESE_FIRST,
        color=0xE60012,
        timezone=JST,
        date_format="%Y-%m-%d",
        package_name="jp.co.dalcomsoft.superstarldh",
        version_floor="1.0.1",
        manifest_url="https://superstar-ldh-jp-real.s3.amazonaws.com/version/manifest/{version}.txt",
        has_bonuses=True,
        app_store=AppStoreLookup(6752320672, "jp"),
    ),
    Game(
        key="PH",
        name="SuperStar PHILIPPINES",
        languages=ENGLISH_FIRST,
        color=0x04102D,
        timezone=PHT,
        date_format="%d-%m-%Y",
        package_name="com.dalcomsoft.ssph",
        version_floor="3.14.0",
        manifest_url="https://superstar-philippines.s3.amazonaws.com/version/real/manifest/{version}.txt",
        has_bonuses=True,
        base_score=PRISM_BASE_SCORE,
        forward=ForwardConfig(
            maintenance_channel_id=1413706748833038498,
            scheduled_channel_id=1418938997165527171,
            targets={
                SSRG_GUILD: 1156462287943630930,
                TEST_GUILD: 1413706686346301480,
            },
        ),
        app_store=AppStoreLookup(6451133069, "us"),
        dalcom_authorization="WWFeNnhxVldSJWFkVWp4Z3ViOFY6WmJRcy1uZ1YyQQ==",
        google_audience="234980834479-creie63p99odjttcv9pvifjelsuf983i",
    ),
)

GAMES: Mapping[str, Game] = MappingProxyType({game.key: game for game in _GAMES})

if len(GAMES) != len(_GAMES):
    raise RuntimeError("Duplicate game key in the registry.")
