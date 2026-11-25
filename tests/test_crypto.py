import base64
import gzip
import json

import pytest
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad

from games.api.crypto import Cipher, CryptoError, random_iv

KEY = b"0123456789abcdef0123456789abcdef"
cipher = Cipher(KEY)


def test_the_key_must_be_an_aes_size():
    for size in (16, 24, 32):
        Cipher(b"k" * size)
    with pytest.raises(CryptoError):
        Cipher(b"short")


def test_server_bodies_round_trip_through_base64_cbc():
    iv = random_iv()
    assert len(iv) == 16 and iv.isalpha() and iv.isupper()
    text = cipher.encrypt_cbc('{"class":"Platform"}', iv)
    assert base64.b64decode(text)  # it is base64
    assert cipher.decrypt_cbc(text, iv) == b'{"class":"Platform"}'
    assert cipher.decrypt_cbc(text, iv.encode()) == b'{"class":"Platform"}'
    with pytest.raises(CryptoError):
        cipher.encrypt_cbc("x", "short")  # the IV must be 16 bytes
    with pytest.raises(CryptoError):
        cipher.decrypt_cbc("!!not base64!!", iv)
    with pytest.raises(CryptoError):
        cipher.decrypt_cbc(
            base64.b64encode(b"x" * 16), "ABCDEFGHIJKLMNOP"
        )  # bad padding (a fixed IV: a random one is valid by chance 1 in 256)


def test_binary_bodies_carry_their_iv_in_front():
    sealed = cipher.seal(b"hello")
    assert len(sealed) == 32 and cipher.unseal(sealed) == b"hello"
    assert cipher.seal(b"hello") != sealed  # a fresh IV every time
    assert cipher.unseal(cipher.seal(b"")) == b""
    for bad in (b"", b"x" * 31, b"x" * 33, b"x" * 48):
        with pytest.raises(CryptoError):
            cipher.unseal(bad)
    # Another key cannot read it.
    with pytest.raises(CryptoError):
        Cipher(b"z" * 32).unseal(cipher.seal(b"hello" * 10))


def table_bytes(items, key=KEY):
    raw = AES.new(key, AES.MODE_ECB).encrypt(pad(json.dumps(items).encode(), 16))
    return gzip.compress(base64.b64encode(raw))


def test_a_data_table_is_gzip_of_base64_of_ecb_and_keyed_by_code():
    items = [{"code": 5, "name": "a"}, {"code": 7, "name": "b"}]
    assert cipher.decode_table(table_bytes(items)) == {"5": items[0], "7": items[1]}


def test_bad_tables_are_crypto_errors():
    for content in (
        b"not gzip",
        gzip.compress(b"not base64 !!"),
        table_bytes([{"name": "no code"}]),
        table_bytes({"not": "a list"}),
        table_bytes([{"code": 1}], key=b"z" * 32),
    ):
        with pytest.raises(CryptoError):
            cipher.decode_table(content)
