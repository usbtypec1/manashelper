from dataclasses import dataclass

from manashelper.modules.obis.application.credentials import ObisCredentialsQuery
from manashelper.modules.obis.application.models import PendingObisLogin, StoredCredentials
from manashelper.modules.obis.application.ports import (
    CredentialsStore,
    ObisAuthenticator,
    PasswordCipher,
    SnapshotStore,
)
from manashelper.modules.obis.application.sessions import ObisSessions
from manashelper.modules.obis.errors import DecryptionError, ObisLoginError


@dataclass(frozen=True, slots=True)
class CompleteObisLoginUseCase:
    credentials: ObisCredentialsQuery
    store: CredentialsStore
    authenticator: ObisAuthenticator
    cipher: PasswordCipher
    snapshots: SnapshotStore
    sessions: ObisSessions

    async def execute(self, user_id: int, pending: PendingObisLogin, captcha_code: str) -> None:
        await self.store.lock(user_id)
        stored = await self.credentials.get_stored_credentials(user_id)
        try:
            password = self.cipher.decrypt(pending.encrypted_password)
        except DecryptionError as error:
            raise ObisLoginError("OBIS password cannot be decrypted") from error
        # Login failures leave both saved credentials and the previous session untouched.
        cookies = await self.authenticator.complete_login(
            pending.attempt, pending.student_number, password, captcha_code
        )
        credentials = StoredCredentials(pending.student_number, pending.encrypted_password)
        if credentials != stored:
            await self.store.save(user_id, credentials)
            await self.snapshots.reset(user_id)
        await self.sessions.save(user_id, cookies)
