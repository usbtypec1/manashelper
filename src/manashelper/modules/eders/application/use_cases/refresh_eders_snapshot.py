import hashlib
from dataclasses import dataclass

from manashelper.modules.eders.application.models import (
    EdersSnapshot,
)
from manashelper.modules.eders.application.tracking import EdersTrackingService
from manashelper.modules.eders.errors import EdersLoginError
from manashelper.modules.eders.infrastructure.client import EdersClient
from manashelper.modules.obis.application.access import ObisAccessService
from manashelper.modules.obis.application.credentials import ObisCredentialsQuery


@dataclass(frozen=True, slots=True)
class RefreshEdersSnapshotUseCase:
    credentials: ObisCredentialsQuery
    eders_client: EdersClient
    eders_tracking_service: EdersTrackingService
    obis_access: ObisAccessService

    async def execute(self, user_id: int) -> EdersSnapshot:
        await self.eders_tracking_service.get_settings(user_id)
        await self.eders_tracking_service.lock(user_id)
        student_number = await self.credentials.get_student_number(user_id)
        try:
            snapshot = await self.eders_client.fetch_snapshot(student_number)
        except EdersLoginError:

            async def fetch_via_sso(cookies: dict[str, str]) -> EdersSnapshot:
                return await self.eders_client.fetch_snapshot(student_number, cookies)

            snapshot = await self.obis_access.with_session(user_id, fetch_via_sso)
        marker = hashlib.sha256(student_number.encode()).hexdigest()
        return await self.eders_tracking_service.observe(user_id, marker, snapshot)
