from dataclasses import dataclass

from manashelper.modules.obis.application.credentials import ObisCredentialsQuery
from manashelper.modules.obis.application.models import StoredCredentials
from manashelper.modules.obis.application.ports import (
    CredentialsStore,
    CredentialsVerifier,
    PasswordCipher,
    SnapshotStore,
)


@dataclass(frozen=True, slots=True)
class SaveObisCredentialsUseCase:
    credentials: ObisCredentialsQuery
    store: CredentialsStore
    verifier: CredentialsVerifier
    cipher: PasswordCipher
    snapshots: SnapshotStore

    async def execute(self, user_id: int, student_number: str, plain_password: str) -> None:
        await self.store.lock(user_id)
        await self.credentials.get_stored_credentials(user_id)
        await self.verifier.verify_credentials(student_number, plain_password)
        encrypted_password = self.cipher.encrypt(plain_password)
        await self.store.save(user_id, StoredCredentials(student_number, encrypted_password))
        await self.snapshots.reset(user_id)
