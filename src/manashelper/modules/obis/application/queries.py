from dataclasses import dataclass

from manashelper.modules.obis.application.credentials import ObisCredentialsQuery, get_results_credentials
from manashelper.modules.obis.application.models import LessonAttendanceModel, LessonExamsModel, Snapshot
from manashelper.modules.obis.application.ports import SnapshotStore
from manashelper.modules.obis.application.sessions import ObisSessions
from manashelper.modules.obis.errors import ObisSessionExpiredError, ObisSnapshotNotReadyError


@dataclass(frozen=True, slots=True)
class ObisResultsQuery:
    credentials: ObisCredentialsQuery
    snapshots: SnapshotStore
    sessions: ObisSessions

    async def get_exam_grades(self, user_id: int) -> Snapshot[LessonExamsModel]:
        credentials = await get_results_credentials(self.credentials, user_id)
        snapshot = await self.snapshots.get_exam_grades(user_id, credentials.credential_marker)
        return await self._require_snapshot(user_id, snapshot)

    async def get_attendance(self, user_id: int) -> Snapshot[LessonAttendanceModel]:
        credentials = await get_results_credentials(self.credentials, user_id)
        snapshot = await self.snapshots.get_attendance(user_id, credentials.credential_marker)
        return await self._require_snapshot(user_id, snapshot)

    async def has_session(self, user_id: int) -> bool:
        return await self.sessions.has_session(user_id)

    async def get_poll_user_ids(self) -> list[int]:
        return await self.snapshots.get_poll_user_ids()

    async def _require_snapshot[T](self, user_id: int, snapshot: Snapshot[T] | None) -> Snapshot[T]:
        if snapshot is not None:
            return snapshot
        # Without a session no refresh will ever prepare the snapshot, so ask for a login instead of waiting.
        if not await self.sessions.has_session(user_id):
            raise ObisSessionExpiredError
        raise ObisSnapshotNotReadyError
