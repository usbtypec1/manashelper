import hashlib
from dataclasses import dataclass

from manashelper.modules.eders.application.models import ActivityKind
from manashelper.modules.eders.application.tracking import EdersTrackingService
from manashelper.modules.eders.errors import EdersCompletionUnavailableError, EdersLoginError
from manashelper.modules.eders.infrastructure.client import EdersClient
from manashelper.modules.obis.application.access import ObisAccessService
from manashelper.modules.obis.application.credentials import ObisCredentialsQuery


@dataclass(frozen=True, slots=True)
class SetActivityCompletionUseCase:
    credentials: ObisCredentialsQuery
    eders_client: EdersClient
    tracking: EdersTrackingService
    obis_access: ObisAccessService

    async def execute(self, user_id: int, activity_id: int, completed: bool) -> None:
        await self.tracking.get_settings(user_id)
        await self.tracking.lock(user_id)
        student_number = await self.credentials.get_student_number(user_id)
        marker = hashlib.sha256(student_number.encode()).hexdigest()
        snapshot = await self.tracking.get_snapshot(user_id, marker)
        activity = next((item for item in snapshot.activities if item.id == activity_id), None)
        if activity is None or activity.kind not in {ActivityKind.ASSIGNMENT, ActivityKind.QUIZ}:
            raise EdersCompletionUnavailableError
        if not activity.manual_completion:
            raise EdersCompletionUnavailableError
        # Always send the target state: the student may have changed it on the website
        # since the last snapshot. Repeated taps remain idempotent.
        try:
            await self.eders_client.set_activity_completion(student_number, activity_id, completed)
        except EdersLoginError:

            async def complete_via_sso(cookies: dict[str, str]) -> None:
                await self.eders_client.set_activity_completion(student_number, activity_id, completed, cookies)

            await self.obis_access.with_session(user_id, complete_via_sso)
        await self.tracking.set_activity_completion(user_id, marker, activity_id, completed)
