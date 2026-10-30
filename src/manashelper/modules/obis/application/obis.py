import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from manashelper.modules.obis.application.credentials import ObisCredentials, ObisCredentialsService
from manashelper.modules.obis.errors import DecryptionError, ObisSnapshotNotReadyError, UserHasNoCredentialsError
from manashelper.modules.obis.infrastructure.client import ObisClient
from manashelper.modules.obis.infrastructure.parser import (
    ScrapedLessonAttendance,
    ScrapedLessonExams,
    parse_attendance_page,
    parse_exam_grades_page,
)
from manashelper.modules.obis.infrastructure.snapshot import ObisSnapshot
from manashelper.modules.obis.infrastructure.snapshot_repository import ObisSnapshotRepository

THEORY_SKIPS_THRESHOLD = 30.0
PRACTICE_SKIPS_THRESHOLD = 20.0
SKIP_PERCENTAGE_PER_LESSON = 6.25


@dataclass(frozen=True, slots=True)
class ExamModel:
    name: str | None
    score: str | None


@dataclass(frozen=True, slots=True)
class LessonExamsModel:
    lesson_name: str | None
    lesson_code: str | None
    exams: list[ExamModel]


@dataclass(frozen=True, slots=True)
class LessonAttendanceModel:
    lesson_name: str
    lesson_code: str
    theory_skips_percentage: float | None
    practice_skips_percentage: float | None
    theory_skippable: int | None
    practice_skippable: int | None


def _compute_skippable(percentage: float | None, threshold: float) -> int | None:
    if percentage is None:
        return None
    diff = threshold - percentage
    if diff == SKIP_PERCENTAGE_PER_LESSON:
        return 0
    return int(diff / SKIP_PERCENTAGE_PER_LESSON)


def _to_exams_model(lesson: ScrapedLessonExams) -> LessonExamsModel:
    return LessonExamsModel(
        lesson_name=lesson.lesson_name,
        lesson_code=lesson.lesson_code,
        exams=[ExamModel(name=exam.name, score=exam.score) for exam in lesson.exams],
    )


def _to_attendance_model(lesson: ScrapedLessonAttendance) -> LessonAttendanceModel:
    return LessonAttendanceModel(
        lesson_name=lesson.lesson_name,
        lesson_code=lesson.lesson_code,
        theory_skips_percentage=lesson.theory_skips_percentage,
        practice_skips_percentage=lesson.practice_skips_percentage,
        theory_skippable=_compute_skippable(lesson.theory_skips_percentage, THEORY_SKIPS_THRESHOLD),
        practice_skippable=_compute_skippable(lesson.practice_skips_percentage, PRACTICE_SKIPS_THRESHOLD),
    )


class ObisService:
    def __init__(
        self,
        credentials: ObisCredentialsService,
        obis_client: ObisClient,
        snapshots: ObisSnapshotRepository,
    ) -> None:
        self._credentials = credentials
        self._obis_client = obis_client
        self._snapshots = snapshots

    async def save_credentials(self, user_id: int, student_number: str, plain_password: str) -> None:
        await self._credentials.save_credentials(user_id, student_number, plain_password)
        await self._snapshots.reset(user_id)

    async def has_credentials(self, user_id: int) -> bool:
        return await self._credentials.has_credentials(user_id)

    async def clear_credentials(self, user_id: int) -> None:
        await self._credentials.clear_credentials(user_id)
        await self._snapshots.reset(user_id)

    async def get_exam_grades(self, user_id: int) -> list[LessonExamsModel]:
        payload = await self._get_payload(user_id, "grades")
        return [
            LessonExamsModel(row["lesson_name"], row["lesson_code"], [ExamModel(**exam) for exam in row["exams"]])
            for row in json.loads(payload)
        ]

    async def get_attendance(self, user_id: int) -> list[LessonAttendanceModel]:
        return [LessonAttendanceModel(**row) for row in json.loads(await self._get_payload(user_id, "attendance"))]

    async def _get_payload(self, user_id: int, kind: str) -> str:
        credentials = await self._get_credentials(user_id)
        snapshot = await self._snapshots.get(user_id, kind)
        if snapshot is None or snapshot.credential_marker != credentials.credential_marker:
            raise ObisSnapshotNotReadyError
        return snapshot.payload

    async def refresh_exam_grades(self, user_id: int) -> list[LessonExamsModel]:
        await self._credentials.lock(user_id)
        credentials = await self._get_credentials(user_id)
        student_number, plain_password = credentials.student_number, credentials.plain_password
        html = await self._obis_client.fetch_exam_grades_html(student_number, plain_password)
        lessons = [_to_exams_model(lesson) for lesson in parse_exam_grades_page(html)]
        await self._save_snapshot(user_id, "grades", credentials.credential_marker, lessons)
        return lessons

    async def refresh_attendance(self, user_id: int) -> list[LessonAttendanceModel]:
        await self._credentials.lock(user_id)
        credentials = await self._get_credentials(user_id)
        student_number, plain_password = credentials.student_number, credentials.plain_password
        html = await self._obis_client.fetch_attendance_html(student_number, plain_password)
        lessons = [_to_attendance_model(lesson) for lesson in parse_attendance_page(html)]
        await self._save_snapshot(user_id, "attendance", credentials.credential_marker, lessons)
        return lessons

    async def _save_snapshot(
        self, user_id: int, kind: str, marker: str, lessons: list[LessonExamsModel] | list[LessonAttendanceModel]
    ) -> None:
        await self._snapshots.save(
            ObisSnapshot(
                user_id=user_id,
                kind=kind,
                credential_marker=marker,
                payload=json.dumps([asdict(lesson) for lesson in lessons], ensure_ascii=False),
                fetched_at=datetime.now(UTC),
            )
        )

    async def get_poll_user_ids(self) -> list[int]:
        return await self._snapshots.get_poll_user_ids()

    async def _get_credentials(self, user_id: int) -> ObisCredentials:
        try:
            credentials = await self._credentials.get_credentials(user_id)
        except DecryptionError as error:
            raise UserHasNoCredentialsError(user_id) from error
        return credentials
