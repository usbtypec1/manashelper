import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from manashelper.core.config import Settings
from manashelper.platform.web.auth_repository import AdminAuthRepository, AuthenticatedAdmin

COOKIE_NAME = "manashelper_admin"


class AuthenticationError(Exception):
    pass


class ForbiddenError(Exception):
    pass


def token_digest(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def web_origin(settings: Settings) -> str:
    if settings.admin_web_origin is None or settings.admin_web_signing_key is None:
        raise ValueError("Configure MANASHELPER_ADMIN_WEB_ORIGIN and MANASHELPER_ADMIN_WEB_SIGNING_KEY")
    if settings.admin_chat_id <= 0:
        raise ValueError("Administrative web access requires a private admin_chat_id")
    return str(settings.admin_web_origin).rstrip("/")


@dataclass(frozen=True, slots=True)
class LoginSession:
    admin: AuthenticatedAdmin
    cookie: str = field(repr=False)
    csrf: str = field(repr=False)


class AdminAuthService:
    def __init__(self, repository: AdminAuthRepository, settings: Settings) -> None:
        self._repository = repository
        self._settings = settings

    def csrf(self, cookie: str) -> str:
        secret = self._settings.admin_web_signing_key
        if secret is None:
            raise AuthenticationError("Web access is not configured")
        return hmac.new(secret.get_secret_value().encode(), ("csrf:" + cookie).encode(), hashlib.sha256).hexdigest()

    async def issue(self, user_id: int) -> str:
        web_origin(self._settings)
        if user_id != self._settings.admin_chat_id:
            raise ForbiddenError("Administrative access required")
        raw = secrets.token_urlsafe(32)
        await self._repository.issue(token_digest(raw), user_id, datetime.now(UTC) + timedelta(minutes=5))
        return raw

    async def exchange(self, ticket: str) -> LoginSession:
        now = datetime.now(UTC)
        user_id = await self._repository.consume(token_digest(ticket), now, self._settings.admin_chat_id)
        if user_id is None:
            raise AuthenticationError("Login ticket is invalid or expired")
        cookie = secrets.token_urlsafe(32)
        expires_at = now + timedelta(hours=8)
        await self._repository.create_session(token_digest(cookie), user_id, expires_at)
        return LoginSession(AuthenticatedAdmin(user_id, expires_at), cookie, self.csrf(cookie))

    async def authenticate(self, cookie: str | None) -> AuthenticatedAdmin:
        if cookie is None or not 32 <= len(cookie) <= 256:
            raise AuthenticationError("Administrative session required")
        admin = await self._repository.session(token_digest(cookie), datetime.now(UTC), self._settings.admin_chat_id)
        if admin is None:
            raise AuthenticationError("Administrative session is invalid or expired")
        return admin

    async def logout(self, cookie: str) -> None:
        await self._repository.revoke(token_digest(cookie))

    async def purge_expired(self) -> int:
        return await self._repository.purge_expired(datetime.now(UTC))
