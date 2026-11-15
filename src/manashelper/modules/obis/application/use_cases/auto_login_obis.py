from dataclasses import dataclass

from manashelper.modules.obis.application.models import ObisCaptcha
from manashelper.modules.obis.application.ports import CaptchaRecognizer
from manashelper.modules.obis.application.use_cases.complete_obis_login import CompleteObisLoginUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_captcha import RefreshObisCaptchaUseCase
from manashelper.modules.obis.application.use_cases.start_obis_login import StartObisLoginUseCase
from manashelper.modules.obis.errors import ObisCaptchaError


@dataclass(frozen=True, slots=True)
class AutoLoginObisUseCase:
    start: StartObisLoginUseCase
    complete: CompleteObisLoginUseCase
    refresh: RefreshObisCaptchaUseCase
    recognizer: CaptchaRecognizer

    async def execute(
        self, user_id: int, student_number: str | None = None, plain_password: str | None = None
    ) -> ObisCaptcha | None:
        """Authenticate, or return an unsubmitted challenge for the existing manual fallback.

        Only definitive CAPTCHA rejection permits another POST, always with a fresh
        form/session. Credential, transport and unknown-response errors propagate.
        """
        captcha = await self.start.execute(user_id, student_number, plain_password)
        for attempt in range(3):
            if captcha.expected_hash is None:
                return captcha
            answer = await self.recognizer.solve(captcha.image, captcha.expected_hash)
            if answer is not None:
                try:
                    await self.complete.execute(user_id, captcha.pending, answer)
                except ObisCaptchaError:
                    pass
                else:
                    return None
            elif attempt == 2:
                return captcha
            # A rejected form is consumed, even on the last attempt. The fallback
            # must show a fresh image bound to an unsubmitted CSRF/cookie session.
            captcha = await self.refresh.execute(captcha.pending)
        return captcha
