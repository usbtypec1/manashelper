from dataclasses import dataclass

from manashelper.modules.obis.application.credentials import ObisCredentialsQuery
from manashelper.modules.obis.application.models import ObisCaptcha, PendingObisLogin
from manashelper.modules.obis.application.ports import ObisAuthenticator, PasswordCipher
from manashelper.modules.obis.errors import UserHasNoCredentialsError


@dataclass(frozen=True, slots=True)
class StartObisLoginUseCase:
    credentials: ObisCredentialsQuery
    authenticator: ObisAuthenticator
    cipher: PasswordCipher

    async def execute(
        self, user_id: int, student_number: str | None = None, plain_password: str | None = None
    ) -> ObisCaptcha:
        """Open an OBIS login form; without new credentials, log in again with the saved account."""
        stored = await self.credentials.get_stored_credentials(user_id)
        if student_number is None or plain_password is None:
            if not stored.student_number or not stored.encrypted_password:
                raise UserHasNoCredentialsError(user_id)
            student_number, encrypted_password = stored.student_number, stored.encrypted_password
        else:
            encrypted_password = self.cipher.encrypt(plain_password)
        challenge = await self.authenticator.start_login()
        pending = PendingObisLogin(student_number, encrypted_password, challenge.attempt)
        return ObisCaptcha(pending, challenge.captcha_image)
