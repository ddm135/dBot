import base64
import gzip
import json
import os
import secrets
import string
import zlib
from typing import Any

from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad, unpad

IV_LENGTH = AES.block_size  # 16
_IV_ALPHABET = string.ascii_uppercase


class CryptoError(ValueError):
    """Data could not be decoded or decrypted."""


def random_iv() -> str:
    return "".join(secrets.choice(_IV_ALPHABET) for _ in range(IV_LENGTH))


def _iv_bytes(iv: str | bytes) -> bytes:
    raw = iv.encode() if isinstance(iv, str) else iv
    if len(raw) != IV_LENGTH:
        raise CryptoError(f"The IV must be {IV_LENGTH} bytes, not {len(raw)}.")
    return raw


class Cipher:
    """AES as the games use it: ECB for the tables, CBC for the server calls."""

    def __init__(self, key: bytes) -> None:
        if len(key) not in AES.key_size:
            raise CryptoError(
                f"The AES key must be 16, 24 or 32 bytes long, not {len(key)}."
            )
        self._key = key

    def _encrypt_cbc(self, data: bytes, iv: bytes) -> bytes:
        return AES.new(self._key, AES.MODE_CBC, iv).encrypt(pad(data, AES.block_size))

    def _decrypt(self, data: bytes, iv: bytes | None = None) -> bytes:
        """CBC with an IV, ECB without."""
        try:
            cipher = (
                AES.new(self._key, AES.MODE_CBC, iv)
                if iv is not None
                else AES.new(self._key, AES.MODE_ECB)
            )
            return unpad(cipher.decrypt(data), AES.block_size)
        except ValueError as exc:  # bad length or padding
            raise CryptoError(f"Could not decrypt the data: {exc}") from exc

    @staticmethod
    def _base64(data: str | bytes) -> bytes:
        try:
            return base64.b64decode(data)
        except ValueError as exc:  # binascii.Error
            raise CryptoError(f"Could not decrypt the data: {exc}") from exc

    # Text bodies (base64), as the HTTP server and the data tables use them.

    def decrypt_ecb(self, data: str | bytes) -> bytes:
        return self._decrypt(self._base64(data))

    def decrypt_cbc(self, data: str | bytes, iv: str | bytes) -> bytes:
        return self._decrypt(self._base64(data), _iv_bytes(iv))

    def encrypt_cbc(self, data: str | bytes, iv: str | bytes) -> str:
        if isinstance(data, str):
            data = data.encode()
        encrypted = self._encrypt_cbc(data, _iv_bytes(iv))
        return base64.b64encode(encrypted).decode()

    # Binary bodies, as the MagicOnion servers use them: ``IV || ciphertext``.

    def seal(self, data: bytes) -> bytes:
        iv = os.urandom(IV_LENGTH)
        return iv + self._encrypt_cbc(data, iv)

    def unseal(self, payload: bytes) -> bytes:
        if len(payload) < 2 * IV_LENGTH:
            raise CryptoError(f"The encrypted body is too short: {len(payload)}.")
        return self._decrypt(payload[IV_LENGTH:], payload[:IV_LENGTH])

    def decode_table(self, content: bytes) -> dict[str, dict[str, Any]]:
        try:
            plain = self.decrypt_ecb(gzip.decompress(content))
            return {str(item["code"]): item for item in json.loads(plain)}
        except CryptoError:
            raise
        except (OSError, EOFError, zlib.error, KeyError, TypeError, ValueError) as exc:
            raise CryptoError(f"The data table is not valid: {exc!r}") from exc
