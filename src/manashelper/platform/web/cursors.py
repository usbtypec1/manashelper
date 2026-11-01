import base64
import hashlib
import hmac
import json
from typing import cast


class InvalidCursorError(Exception):
    pass


class CursorCodec:
    def __init__(self, secret: str) -> None:
        self._secret = secret.encode()

    def encode(self, scope: str, last: str | int) -> str:
        payload = (
            base64.urlsafe_b64encode(json.dumps([1, scope, last], separators=(",", ":")).encode()).decode().rstrip("=")
        )
        signature = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()
        return payload + "." + signature

    def decode(self, cursor: str | None, scope: str) -> str | int | None:
        if cursor is None:
            return None
        try:
            payload, signature = cursor.split(".")
            expected = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError
            version, stored_scope, last = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
            if version != 1 or stored_scope != scope or type(last) not in (str, int):
                raise ValueError
            return cast(str | int, last)
        except (ValueError, TypeError, UnicodeError):
            raise InvalidCursorError("Cursor is invalid for this resource") from None
