from base64 import b64decode, b64encode
from typing import TYPE_CHECKING

from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad, unpad
from discord.ext import commands

from .commons import AES_KEY

if TYPE_CHECKING:
    from dBot import dBot


class Cryptographic(commands.Cog):
    def __init__(self) -> None:
        pass

    @staticmethod
    def decrypt_ecb(data: str | bytes) -> bytes:
        cipher_ecb = AES.new(AES_KEY, AES.MODE_ECB)
        return unpad(cipher_ecb.decrypt(b64decode(data)), AES.block_size)

    @staticmethod
    def decrypt_cbc(data: str | bytes, iv: str | bytes) -> bytes:
        if isinstance(iv, str):
            iv = iv.encode()

        cipher_cbc = AES.new(AES_KEY, AES.MODE_CBC, iv)
        return unpad(cipher_cbc.decrypt(b64decode(data)), AES.block_size)

    @staticmethod
    def encrypt_cbc(data: str | bytes, iv: str | bytes) -> str:
        if isinstance(data, str):
            data = data.encode()
        if isinstance(iv, str):
            iv = iv.encode()

        cipher_cbc = AES.new(AES_KEY, AES.MODE_CBC, iv)
        return b64encode(cipher_cbc.encrypt(pad(data, AES.block_size))).decode()


async def setup(bot: "dBot") -> None:
    await bot.add_cog(Cryptographic())
