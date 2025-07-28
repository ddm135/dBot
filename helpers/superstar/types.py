import random
import string

from .commons import API_VERSION, ASSET_IGNORE, IV_LENGTH


class SuperStarHeaders(dict):
    def __init__(self) -> None:
        super().__init__(
            {
                "X-SuperStar-AES-IV": "".join(
                    random.choices(string.ascii_uppercase, k=IV_LENGTH)
                ),
                "X-SuperStar-Asset-Ignore": ASSET_IGNORE,
                "X-SuperStar-API-Version": API_VERSION,
            }
        )
