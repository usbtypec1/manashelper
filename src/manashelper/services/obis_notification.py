import uuid
from dataclasses import dataclass
from enum import StrEnum

from manashelper.db.models import UserExamGrade, UserLessonAttendance
from manashelper.repositories.user_exam_grade_repository import UserExamGradeRepository
from manashelper.repositories.user_lesson_attendance_repository import UserLessonAttendanceRepository
from manashelper.services.obis import ObisService


@dataclass(frozen=True, slots=True)
class ExamGradeChange:
    lesson_name: str | None
    exam_name: str | None
    score: str


class SkipType(StrEnum):
    THEORY = "theory"
    PRACTICE = "practice"


@dataclass(frozen=True, slots=True)
class LessonSkipChange:
    lesson_name: str
    skip_type: SkipType
    skips_percentage: float
    skippable: int | None


def _has_increased(new_value: float, old_value: float | None) -> bool:
    return old_value is not None and new_value > old_value


class ObisNotificationService:
    def __init__(
        self,
        obis_service: ObisService,
        user_exam_grade_repository: UserExamGradeRepository,
        user_lesson_attendance_repository: UserLessonAttendanceRepository,
    ) -> None:
        self._obis_service = obis_service
        self._user_exam_grade_repository = user_exam_grade_repository
        self._user_lesson_attendance_repository = user_lesson_attendance_repository

    async def check_exam_grade_changes(self, user_id: int) -> list[ExamGradeChange]:
        lessons = await self._obis_service.get_exam_grades(user_id)
        existing_grades = await self._user_exam_grade_repository.get_all_by_user_id(user_id)
        existing_by_key = {(grade.lesson_code, grade.exam_name): grade for grade in existing_grades}

        changes: list[ExamGradeChange] = []
        for lesson in lessons:
            for exam in lesson.exams:
                key = (lesson.lesson_code, exam.name)
                existing = existing_by_key.get(key)
                if existing is None:
                    self._user_exam_grade_repository.add(
                        UserExamGrade(
                            id=uuid.uuid4(),
                            user_id=user_id,
                            lesson_code=lesson.lesson_code,
                            exam_name=exam.name,
                            score=exam.score,
                        )
                    )
                    if exam.score is not None:
                        changes.append(
                            ExamGradeChange(lesson_name=lesson.lesson_name, exam_name=exam.name, score=exam.score)
                        )
                elif existing.score != exam.score:
                    existing.score = exam.score
                    if exam.score is not None:
                        changes.append(
                            ExamGradeChange(lesson_name=lesson.lesson_name, exam_name=exam.name, score=exam.score)
                        )
        return changes

    async def check_lesson_skip_changes(self, user_id: int) -> list[LessonSkipChange]:
        lessons = await self._obis_service.get_attendance(user_id)
        existing_records = await self._user_lesson_attendance_repository.get_all_by_user_id(user_id)
        existing_by_lesson_code = {record.lesson_code: record for record in existing_records}

        changes: list[LessonSkipChange] = []
        for lesson in lessons:
            existing = existing_by_lesson_code.get(lesson.lesson_code)
            if existing is None:
                self._user_lesson_attendance_repository.add(
                    UserLessonAttendance(
                        id=uuid.uuid4(),
                        user_id=user_id,
                        lesson_code=lesson.lesson_code,
                        theory_skips_percentage=lesson.theory_skips_percentage,
                        practice_skips_percentage=lesson.practice_skips_percentage,
                    )
                )
                continue

            theory_percentage = lesson.theory_skips_percentage
            if theory_percentage is not None and _has_increased(theory_percentage, existing.theory_skips_percentage):
                changes.append(
                    LessonSkipChange(
                        lesson_name=lesson.lesson_name,
                        skip_type=SkipType.THEORY,
                        skips_percentage=theory_percentage,
                        skippable=lesson.theory_skippable,
                    )
                )

            practice_percentage = lesson.practice_skips_percentage
            if practice_percentage is not None and _has_increased(
                practice_percentage, existing.practice_skips_percentage
            ):
                changes.append(
                    LessonSkipChange(
                        lesson_name=lesson.lesson_name,
                        skip_type=SkipType.PRACTICE,
                        skips_percentage=practice_percentage,
                        skippable=lesson.practice_skippable,
                    )
                )

            existing.theory_skips_percentage = lesson.theory_skips_percentage
            existing.practice_skips_percentage = lesson.practice_skips_percentage

        return changes
