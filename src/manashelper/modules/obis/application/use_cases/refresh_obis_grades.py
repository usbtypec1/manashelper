from dataclasses import dataclass
from datetime import UTC, datetime

from manashelper.modules.obis.application.credentials import ObisCredentialsQuery, get_results_credentials
from manashelper.modules.obis.application.models import LessonExamsModel, RefreshResult, Snapshot
from manashelper.modules.obis.application.notification import ExamGradeChange, compare_exam_grades
from manashelper.modules.obis.application.ports import CredentialsStore, ExamGradeStore, ResultsSource, SnapshotStore


@dataclass(frozen=True, slots=True)
class RefreshObisGradesUseCase:
    credentials: ObisCredentialsQuery
    store: CredentialsStore
    source: ResultsSource
    snapshots: SnapshotStore
    grades: ExamGradeStore

    async def execute(self, user_id: int) -> RefreshResult[LessonExamsModel, ExamGradeChange]:
        await self.store.lock(user_id)
        credentials = await get_results_credentials(self.credentials, user_id)
        lessons = await self.source.fetch_exam_grades(credentials.student_number, credentials.plain_password)
        await self.snapshots.save_exam_grades(
            user_id, Snapshot(credentials.credential_marker, lessons, datetime.now(UTC))
        )
        records, changes = compare_exam_grades(lessons, await self.grades.get_all_by_user_id(user_id))
        await self.grades.save_all(user_id, records)
        return RefreshResult(lessons, changes)
