import hashlib
from dataclasses import dataclass, field

from manashelper.modules.obis.errors import UserHasNoCredentialsError, UserNotFoundError
from manashelper.modules.obis.infrastructure.client import ObisClient
from manashelper.modules.obis.infrastructure.credentials_repository import ObisCredentialsRepository
from manashelper.modules.obis.infrastructure.crypto import CryptoService
from manashelper.modules.users.infrastructure.user import User


@dataclass(frozen=True, slots=True)
class ObisCredentials:
    student_number: str = field(repr=False)
    plain_password: str = field(repr=False)
    credential_marker: str = field(repr=False)


class ObisCredentialsService:
    def __init__(self, repository: ObisCredentialsRepository, client: ObisClient, crypto: CryptoService) -> None:
        self._repository = repository
        self._client = client
        self._crypto = crypto

    async def save_credentials(self, user_id: int, student_number: str, plain_password: str) -> None:
        await self.lock(user_id)
        user = await self._get_user(user_id)
        await self._client.verify_credentials(student_number, plain_password)
        encrypted_password = self._crypto.encrypt(plain_password)
        user.student_number = student_number
        user.encrypted_password = encrypted_password

    async def has_credentials(self, user_id: int) -> bool:
        user = await self._get_user(user_id)
        return user.student_number is not None and user.encrypted_password is not None

    async def clear_credentials(self, user_id: int) -> None:
        await self.lock(user_id)
        user = await self._get_user(user_id)
        user.student_number = None
        user.encrypted_password = None

    async def get_credentials(self, user_id: int) -> ObisCredentials:
        user = await self._get_user(user_id)
        if user.student_number is None or user.encrypted_password is None:
            raise UserHasNoCredentialsError(user_id)
        password = self._crypto.decrypt(user.encrypted_password)
        marker = hashlib.sha256(user.encrypted_password.encode()).hexdigest()
        return ObisCredentials(user.student_number, password, marker)

    async def get_student_number(self, user_id: int) -> str:
        user = await self._get_user(user_id)
        if not user.student_number:
            raise UserHasNoCredentialsError(user_id)
        return user.student_number

    async def lock(self, user_id: int) -> None:
        await self._repository.lock(user_id)

    async def _get_user(self, user_id: int) -> User:
        user = await self._repository.get_by_user_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return user
