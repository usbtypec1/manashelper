import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from manashelper.modules.obis.application.models import StoredObisSession
from manashelper.modules.obis.application.ports import PasswordCipher, SessionStore
from manashelper.modules.obis.errors import DecryptionError, ObisSessionExpiredError


@dataclass(frozen=True, slots=True)
class ObisSessions:
    """Own the saved OBIS login session; its cookies are bearer secrets and stay encrypted at rest."""

    store: SessionStore
    cipher: PasswordCipher

    async def has_session(self, user_id: int) -> bool:
        return await self.store.get(user_id) is not None

    async def get_cookies(self, user_id: int) -> dict[str, str]:
        session = await self.store.get(user_id)
        if session is None:
            raise ObisSessionExpiredError
        try:
            cookies = json.loads(self.cipher.decrypt(session.encrypted_cookies))
        except (DecryptionError, ValueError) as error:
            raise ObisSessionExpiredError from error
        if not isinstance(cookies, dict):
            raise ObisSessionExpiredError
        return {str(name): str(value) for name, value in cookies.items()}

    async def save(self, user_id: int, cookies: dict[str, str]) -> None:
        encrypted = self.cipher.encrypt(json.dumps(cookies, sort_keys=True))
        await self.store.save(user_id, StoredObisSession(encrypted, datetime.now(UTC)))

    async def expire(self, user_id: int) -> timedelta | None:
        """Forget the session; return its age when one existed."""
        session = await self.store.delete(user_id)
        return None if session is None else datetime.now(UTC) - session.created_at
