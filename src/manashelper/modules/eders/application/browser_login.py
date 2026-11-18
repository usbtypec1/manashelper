import hashlib
import secrets
import time
from dataclasses import dataclass, field

from manashelper.modules.eders.errors import InvalidEdersLoginLinkError
from manashelper.modules.obis.application.models import StoredCredentials

LOGIN_LINK_SECONDS = 60


def browser_login_marker(credentials: StoredCredentials) -> str:
    value = f"{credentials.student_number}\0{credentials.encrypted_password or ''}"
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class EdersLoginGrant:
    user_id: int
    credential_marker: str = field(repr=False)
    expires_at: float


class EdersLoginTokens:
    """Ephemeral bearer grants for the documented single-process deployment.

    Mutation is synchronous: consumption happens before any await, including when
    concurrent HTTP requests use the same link. Restarting revokes every grant.
    """

    def __init__(self) -> None:
        self._grants: dict[str, EdersLoginGrant] = {}

    def issue(self, user_id: int, credential_marker: str) -> str:
        now = time.monotonic()
        self._grants = {
            digest: grant
            for digest, grant in self._grants.items()
            if grant.expires_at > now and grant.user_id != user_id
        }
        token = secrets.token_urlsafe(32)
        self._grants[hashlib.sha256(token.encode()).hexdigest()] = EdersLoginGrant(
            user_id, credential_marker, now + LOGIN_LINK_SECONDS
        )
        return token

    def consume(self, token: str) -> EdersLoginGrant:
        if len(token) != 43 or any(
            char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-" for char in token
        ):
            raise InvalidEdersLoginLinkError
        grant = self._grants.pop(hashlib.sha256(token.encode()).hexdigest(), None)
        if grant is None or grant.expires_at <= time.monotonic():
            raise InvalidEdersLoginLinkError
        return grant
