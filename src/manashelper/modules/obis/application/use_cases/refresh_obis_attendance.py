from dataclasses import dataclass
from datetime import UTC, datetime

from manashelper.modules.gamification.application.use_cases.record_attendance import RecordAttendanceUseCase
from manashelper.modules.obis.application.attendance import to_attendance_model
from manashelper.modules.obis.application.credentials import ObisCredentialsQuery, get_results_credentials
from manashelper.modules.obis.application.models import LessonAttendanceModel, RefreshResult, Snapshot
from manashelper.modules.obis.application.notification import LessonSkipChange, compare_attendance
from manashelper.modules.obis.application.ports import AttendanceStore, CredentialsStore, ResultsSource, SnapshotStore
from manashelper.modules.obis.application.sessions import ObisSessions


@dataclass(frozen=True, slots=True)
class RefreshObisAttendanceUseCase:
    credentials: ObisCredentialsQuery
    store: CredentialsStore
    source: ResultsSource
    sessions: ObisSessions
    snapshots: SnapshotStore
    attendance: AttendanceStore
    record: RecordAttendanceUseCase

    async def execute(self, user_id: int) -> RefreshResult[LessonAttendanceModel, LessonSkipChange]:
        await self.store.lock(user_id)
        credentials = await get_results_credentials(self.credentials, user_id)
        records = await self.source.fetch_attendance(await self.sessions.get_cookies(user_id))
        lessons = [to_attendance_model(record) for record in records]
        await self.snapshots.save_attendance(
            user_id, Snapshot(credentials.credential_marker, lessons, datetime.now(UTC))
        )
        baseline, changes = compare_attendance(lessons, await self.attendance.get_all_by_user_id(user_id))
        await self.attendance.save_all(user_id, baseline)
        await self.record.execute(user_id, credentials.student_number, lessons)
        return RefreshResult(lessons, changes)
