import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from manashelper.config import Settings

_NONCE_LENGTH = 12


class DecryptionError(Exception):
    pass


class CryptoService:
    def __init__(self, settings: Settings) -> None:
        self._aesgcm = AESGCM(base64.b64decode(settings.obis_encryption_key))

    def encrypt(self, plain_text: str) -> str:
        nonce = os.urandom(_NONCE_LENGTH)
        ciphertext = self._aesgcm.encrypt(nonce, plain_text.encode("utf-8"), None)
        return base64.b64encode(nonce + ciphertext).decode("ascii")

    def decrypt(self, encrypted_text: str) -> str:
        try:
            raw = base64.b64decode(encrypted_text)
            nonce, ciphertext = raw[:_NONCE_LENGTH], raw[_NONCE_LENGTH:]
            return self._aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
        except Exception as error:
            raise DecryptionError("Failed to decrypt value") from error
