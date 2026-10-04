import os

AES_KEY = os.getenv("AES_KEY").encode()  # type: ignore[union-attr]
