import json
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.obis.application.models import ExamModel, LessonAttendanceModel, LessonExamsModel, Snapshot
from manashelper.modules.obis.infrastructure.models.auth_state import ObisAuthState
from manashelper.modules.obis.infrastructure.models.snapshot import ObisSnapshot
from manashelper.modules.obis.infrastructure.models.user_exam_grade import UserExamGrade
from manashelper.modules.obis.infrastructure.models.user_lesson_attendance import UserLessonAttendance
from manashelper.modules.users.infrastructure.models.user import User


class ObisSnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _get(self, user_id: int, kind: str) -> ObisSnapshot | None:
        return await self._session.get(ObisSnapshot, (user_id, kind), populate_existing=True)

    async def get_exam_grades(self, user_id: int, marker: str) -> Snapshot[LessonExamsModel] | None:
        snapshot = await self._get(user_id, "grades")
        if snapshot is None or snapshot.credential_marker != marker:
            return None
        return Snapshot(
            snapshot.credential_marker,
            [
                LessonExamsModel(row["lesson_name"], row["lesson_code"], [ExamModel(**exam) for exam in row["exams"]])
                for row in json.loads(snapshot.payload)
            ],
            snapshot.fetched_at,
        )

    async def get_attendance(self, user_id: int, marker: str) -> Snapshot[LessonAttendanceModel] | None:
        snapshot = await self._get(user_id, "attendance")
        if snapshot is None or snapshot.credential_marker != marker:
            return None
        return Snapshot(
            snapshot.credential_marker,
            [LessonAttendanceModel(**row) for row in json.loads(snapshot.payload)],
            snapshot.fetched_at,
        )

    async def save_exam_grades(self, user_id: int, snapshot: Snapshot[LessonExamsModel]) -> None:
        await self._save(user_id, "grades", snapshot)

    async def save_attendance(self, user_id: int, snapshot: Snapshot[LessonAttendanceModel]) -> None:
        await self._save(user_id, "attendance", snapshot)

    async def _save[T: (LessonExamsModel, LessonAttendanceModel)](
        self, user_id: int, kind: str, snapshot: Snapshot[T]
    ) -> None:
        await self._session.merge(
            ObisSnapshot(
                user_id=user_id,
                kind=kind,
                credential_marker=snapshot.credential_marker,
                payload=json.dumps([asdict(lesson) for lesson in snapshot.lessons], ensure_ascii=False),
                fetched_at=snapshot.fetched_at,
            )
        )

    async def reset(self, user_id: int) -> None:
        # A new account must also start notification comparisons from a silent baseline.
        for model in (ObisSnapshot, UserExamGrade, UserLessonAttendance):
            await self._session.execute(delete(model).where(model.user_id == user_id))

    async def get_poll_user_ids(self) -> list[int]:
        now = datetime.now(UTC)
        query = (
            select(User.id)
            .outerjoin(ObisAuthState, ObisAuthState.user_id == User.id)
            .where(
                User.student_number.is_not(None),
                User.student_number != "",
                User.encrypted_password.is_not(None),
                User.encrypted_password != "",
                or_(
                    ObisAuthState.user_id.is_(None),
                    and_(
                        ObisAuthState.manual_required.is_(False),
                        or_(ObisAuthState.retry_at.is_(None), ObisAuthState.retry_at <= now),
                    ),
                    and_(ObisAuthState.manual_required.is_(True), ObisAuthState.notified.is_(False)),
                ),
            )
        )
        return list((await self._session.scalars(query)).all())
