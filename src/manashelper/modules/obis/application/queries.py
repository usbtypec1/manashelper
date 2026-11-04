from dataclasses import dataclass

from manashelper.modules.obis.application.credentials import ObisCredentialsQuery, get_results_credentials
from manashelper.modules.obis.application.models import LessonAttendanceModel, LessonExamsModel
from manashelper.modules.obis.application.ports import SnapshotStore
from manashelper.modules.obis.errors import ObisSnapshotNotReadyError


@dataclass(frozen=True, slots=True)
class ObisResultsQuery:
    credentials: ObisCredentialsQuery
    snapshots: SnapshotStore

    async def get_exam_grades(self, user_id: int) -> list[LessonExamsModel]:
        credentials = await get_results_credentials(self.credentials, user_id)
        return _snapshot_lessons(await self.snapshots.get_exam_grades(user_id, credentials.credential_marker))

    async def get_attendance(self, user_id: int) -> list[LessonAttendanceModel]:
        credentials = await get_results_credentials(self.credentials, user_id)
        return _snapshot_lessons(await self.snapshots.get_attendance(user_id, credentials.credential_marker))

    async def get_poll_user_ids(self) -> list[int]:
        return await self.snapshots.get_poll_user_ids()


def _snapshot_lessons[T](lessons: list[T] | None) -> list[T]:
    if lessons is None:
        raise ObisSnapshotNotReadyError
    return lessons
