"""Authenticated encryption of short-lived inputs, bound to their execution owner."""

import base64
import binascii
import os
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from manashelper.core.config import Settings

_NONCE_BYTES = 12


class SecretUnavailableError(Exception):
    def __init__(self) -> None:
        super().__init__("Secret is unavailable")


class SecretCodec:
    def __init__(self, settings: Settings) -> None:
        try:
            key = base64.b64decode(settings.obis_encryption_key, validate=True)
            self._cipher = AESGCM(key)
        except (ValueError, binascii.Error):
            raise ValueError("Secret encryption key is invalid") from None

    @staticmethod
    def _owner(secret_id: UUID, session_id: UUID, user_id: int, chat_id: int) -> bytes:
        return f"{secret_id}:{session_id}:{user_id}:{chat_id}".encode("ascii")

    def encrypt(self, plaintext: str, secret_id: UUID, session_id: UUID, user_id: int, chat_id: int) -> str:
        nonce = os.urandom(_NONCE_BYTES)
        try:
            ciphertext = self._cipher.encrypt(
                nonce, plaintext.encode("utf-8"), self._owner(secret_id, session_id, user_id, chat_id)
            )
        except (ValueError, UnicodeError):
            raise SecretUnavailableError from None
        return base64.b64encode(nonce + ciphertext).decode("ascii")

    def decrypt(self, ciphertext: str, secret_id: UUID, session_id: UUID, user_id: int, chat_id: int) -> str:
        try:
            raw = base64.b64decode(ciphertext, validate=True)
            if len(raw) < _NONCE_BYTES + 16:
                raise SecretUnavailableError
            return self._cipher.decrypt(
                raw[:_NONCE_BYTES], raw[_NONCE_BYTES:], self._owner(secret_id, session_id, user_id, chat_id)
            ).decode("utf-8")
        except (ValueError, UnicodeError, binascii.Error, InvalidTag):
            raise SecretUnavailableError from None
