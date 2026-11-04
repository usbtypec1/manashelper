from dataclasses import dataclass, replace
from enum import StrEnum

from manashelper.modules.obis.application.models import (
    AttendanceBaseline,
    ExamGradeRecord,
    LessonAttendanceModel,
    LessonExamsModel,
)


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


def compare_exam_grades(
    lessons: list[LessonExamsModel], existing_grades: list[ExamGradeRecord]
) -> tuple[list[ExamGradeRecord], list[ExamGradeChange]]:
    existing_by_key = {(grade.lesson_code, grade.exam_name): grade for grade in existing_grades}
    records: list[ExamGradeRecord] = []
    changes: list[ExamGradeChange] = []
    for lesson in lessons:
        for exam in lesson.exams:
            key = (lesson.lesson_code, exam.name)
            existing = existing_by_key.get(key)
            if existing is None:
                records.append(ExamGradeRecord(None, lesson.lesson_code, exam.name, exam.score))
                if existing_grades and exam.score is not None:
                    changes.append(ExamGradeChange(lesson.lesson_name, exam.name, exam.score))
            elif existing.score != exam.score:
                updated = replace(existing, score=exam.score)
                records.append(updated)
                existing_by_key[key] = updated
                if exam.score is not None:
                    changes.append(ExamGradeChange(lesson.lesson_name, exam.name, exam.score))
    return records, changes


def compare_attendance(
    lessons: list[LessonAttendanceModel], existing_records: list[AttendanceBaseline]
) -> tuple[list[AttendanceBaseline], list[LessonSkipChange]]:
    existing_by_lesson_code = {record.lesson_code: record for record in existing_records}
    records: list[AttendanceBaseline] = []
    changes: list[LessonSkipChange] = []
    for lesson in lessons:
        existing = existing_by_lesson_code.get(lesson.lesson_code)
        if existing is None:
            records.append(
                AttendanceBaseline(
                    None, lesson.lesson_code, lesson.theory_skips_percentage, lesson.practice_skips_percentage
                )
            )
            continue

        theory_percentage = lesson.theory_skips_percentage
        if theory_percentage is not None and _has_increased(theory_percentage, existing.theory_skips_percentage):
            changes.append(
                LessonSkipChange(lesson.lesson_name, SkipType.THEORY, theory_percentage, lesson.theory_skippable)
            )

        practice_percentage = lesson.practice_skips_percentage
        if practice_percentage is not None and _has_increased(practice_percentage, existing.practice_skips_percentage):
            changes.append(
                LessonSkipChange(lesson.lesson_name, SkipType.PRACTICE, practice_percentage, lesson.practice_skippable)
            )

        updated = replace(
            existing,
            theory_skips_percentage=lesson.theory_skips_percentage,
            practice_skips_percentage=lesson.practice_skips_percentage,
        )
        if updated != existing:
            records.append(updated)
        existing_by_lesson_code[lesson.lesson_code] = updated

    return records, changes
