from dataclasses import dataclass, replace

from manashelper.modules.obis.application.models import ObisCaptcha, PendingObisLogin
from manashelper.modules.obis.application.ports import ObisAuthenticator


@dataclass(frozen=True, slots=True)
class RefreshObisCaptchaUseCase:
    authenticator: ObisAuthenticator

    async def execute(self, pending: PendingObisLogin) -> ObisCaptcha:
        # A fresh form also recovers from an expired CSRF token or server-side captcha state.
        challenge = await self.authenticator.start_login()
        return ObisCaptcha(replace(pending, attempt=challenge.attempt), challenge.captcha_image)
