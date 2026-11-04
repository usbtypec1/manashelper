import hashlib
from dataclasses import dataclass, field

from manashelper.modules.obis.application.models import StoredCredentials
from manashelper.modules.obis.application.ports import CredentialsStore, PasswordCipher
from manashelper.modules.obis.errors import DecryptionError, UserHasNoCredentialsError, UserNotFoundError


@dataclass(frozen=True, slots=True)
class ObisCredentials:
    student_number: str = field(repr=False)
    plain_password: str = field(repr=False)
    credential_marker: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ObisCredentialsQuery:
    repository: CredentialsStore
    crypto: PasswordCipher

    async def has_credentials(self, user_id: int) -> bool:
        user = await self.get_stored_credentials(user_id)
        return user.student_number is not None and user.encrypted_password is not None

    async def get_credentials(self, user_id: int) -> ObisCredentials:
        user = await self.get_stored_credentials(user_id)
        if user.student_number is None or user.encrypted_password is None:
            raise UserHasNoCredentialsError(user_id)
        password = self.crypto.decrypt(user.encrypted_password)
        marker = hashlib.sha256(user.encrypted_password.encode()).hexdigest()
        return ObisCredentials(user.student_number, password, marker)

    async def get_student_number(self, user_id: int) -> str:
        user = await self.get_stored_credentials(user_id)
        if not user.student_number:
            raise UserHasNoCredentialsError(user_id)
        return user.student_number

    async def get_stored_credentials(self, user_id: int) -> StoredCredentials:
        user = await self.repository.get_by_user_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return user


async def get_results_credentials(query: ObisCredentialsQuery, user_id: int) -> ObisCredentials:
    try:
        return await query.get_credentials(user_id)
    except DecryptionError as error:
        raise UserHasNoCredentialsError(user_id) from error
