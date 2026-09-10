from dataclasses import dataclass

from manashelper.repositories.user_repository import UserRepository
from manashelper.scraping.obis_client import ObisClient
from manashelper.scraping.obis_parser import (
    ScrapedLessonAttendance,
    ScrapedLessonExams,
    parse_attendance_page,
    parse_exam_grades_page,
)
from manashelper.services.crypto_service import CryptoService, DecryptionError

THEORY_SKIPS_THRESHOLD = 30.0
PRACTICE_SKIPS_THRESHOLD = 20.0
SKIP_PERCENTAGE_PER_LESSON = 6.25


class UserNotFoundError(Exception):
    def __init__(self, user_id: int) -> None:
        super().__init__(f"User {user_id} not found")
        self.user_id = user_id


class UserHasNoCredentialsError(Exception):
    def __init__(self, user_id: int) -> None:
        super().__init__(f"User {user_id} has no OBIS credentials")
        self.user_id = user_id


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


class ObisService:
    def __init__(
        self,
        user_repository: UserRepository,
        obis_client: ObisClient,
        crypto_service: CryptoService,
    ) -> None:
        self._user_repository = user_repository
        self._obis_client = obis_client
        self._crypto_service = crypto_service

    async def save_credentials(self, user_id: int, student_number: str, plain_password: str) -> None:
        user = await self._user_repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)

        await self._obis_client.verify_credentials(student_number, plain_password)

        user.student_number = student_number
        user.encrypted_password = self._crypto_service.encrypt(plain_password)

    async def has_credentials(self, user_id: int) -> bool:
        user = await self._user_repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return user.student_number is not None and user.encrypted_password is not None

    async def clear_credentials(self, user_id: int) -> None:
        user = await self._user_repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        user.student_number = None
        user.encrypted_password = None

    async def get_exam_grades(self, user_id: int) -> list[LessonExamsModel]:
        student_number, plain_password = await self._get_credentials(user_id)
        html = await self._obis_client.fetch_exam_grades_html(student_number, plain_password)
        return [self._to_exams_model(lesson) for lesson in parse_exam_grades_page(html)]

    async def get_attendance(self, user_id: int) -> list[LessonAttendanceModel]:
        student_number, plain_password = await self._get_credentials(user_id)
        html = await self._obis_client.fetch_attendance_html(student_number, plain_password)
        return [self._to_attendance_model(lesson) for lesson in parse_attendance_page(html)]

    async def _get_credentials(self, user_id: int) -> tuple[str, str]:
        user = await self._user_repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        if user.student_number is None or user.encrypted_password is None:
            raise UserHasNoCredentialsError(user_id)

        try:
            plain_password = self._crypto_service.decrypt(user.encrypted_password)
        except DecryptionError as error:
            raise UserHasNoCredentialsError(user_id) from error

        return user.student_number, plain_password

    @staticmethod
    def _to_exams_model(lesson: ScrapedLessonExams) -> LessonExamsModel:
        return LessonExamsModel(
            lesson_name=lesson.lesson_name,
            lesson_code=lesson.lesson_code,
            exams=[ExamModel(name=exam.name, score=exam.score) for exam in lesson.exams],
        )

    @staticmethod
    def _to_attendance_model(lesson: ScrapedLessonAttendance) -> LessonAttendanceModel:
        return LessonAttendanceModel(
            lesson_name=lesson.lesson_name,
            lesson_code=lesson.lesson_code,
            theory_skips_percentage=lesson.theory_skips_percentage,
            practice_skips_percentage=lesson.practice_skips_percentage,
            theory_skippable=_compute_skippable(lesson.theory_skips_percentage, THEORY_SKIPS_THRESHOLD),
            practice_skippable=_compute_skippable(lesson.practice_skips_percentage, PRACTICE_SKIPS_THRESHOLD),
        )


def _compute_skippable(percentage: float | None, threshold: float) -> int | None:
    if percentage is None:
        return None
    diff = threshold - percentage
    if diff == SKIP_PERCENTAGE_PER_LESSON:
        return 0
    return int(diff / SKIP_PERCENTAGE_PER_LESSON)
