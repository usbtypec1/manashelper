from dataclasses import dataclass

from manashelper.modules.obis.application.credentials import ObisCredentialsService
from manashelper.modules.obis.errors import DecryptionError, UserHasNoCredentialsError
from manashelper.modules.obis.infrastructure.client import ObisClient
from manashelper.modules.obis.infrastructure.parser import (
    ScrapedLessonAttendance,
    ScrapedLessonExams,
    parse_attendance_page,
    parse_exam_grades_page,
)

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
    ) -> None:
        self._credentials = credentials
        self._obis_client = obis_client

    async def save_credentials(self, user_id: int, student_number: str, plain_password: str) -> None:
        await self._credentials.save_credentials(user_id, student_number, plain_password)

    async def has_credentials(self, user_id: int) -> bool:
        return await self._credentials.has_credentials(user_id)

    async def clear_credentials(self, user_id: int) -> None:
        await self._credentials.clear_credentials(user_id)

    async def get_exam_grades(self, user_id: int) -> list[LessonExamsModel]:
        student_number, plain_password = await self._get_credentials(user_id)
        html = await self._obis_client.fetch_exam_grades_html(student_number, plain_password)
        return [_to_exams_model(lesson) for lesson in parse_exam_grades_page(html)]

    async def get_attendance(self, user_id: int) -> list[LessonAttendanceModel]:
        student_number, plain_password = await self._get_credentials(user_id)
        html = await self._obis_client.fetch_attendance_html(student_number, plain_password)
        return [_to_attendance_model(lesson) for lesson in parse_attendance_page(html)]

    async def _get_credentials(self, user_id: int) -> tuple[str, str]:
        try:
            credentials = await self._credentials.get_credentials(user_id)
        except DecryptionError as error:
            raise UserHasNoCredentialsError(user_id) from error
        return credentials.student_number, credentials.plain_password
