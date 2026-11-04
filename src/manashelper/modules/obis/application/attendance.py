from manashelper.modules.obis.application.models import AttendanceRecord, LessonAttendanceModel

THEORY_SKIPS_THRESHOLD = 30.0
PRACTICE_SKIPS_THRESHOLD = 20.0
SKIP_PERCENTAGE_PER_LESSON = 6.25


def _compute_skippable(percentage: float | None, threshold: float) -> int | None:
    if percentage is None:
        return None
    diff = threshold - percentage
    if diff == SKIP_PERCENTAGE_PER_LESSON:
        return 0
    return int(diff / SKIP_PERCENTAGE_PER_LESSON)


def to_attendance_model(lesson: AttendanceRecord) -> LessonAttendanceModel:
    return LessonAttendanceModel(
        lesson_name=lesson.lesson_name,
        lesson_code=lesson.lesson_code,
        theory_skips_percentage=lesson.theory_skips_percentage,
        practice_skips_percentage=lesson.practice_skips_percentage,
        theory_skippable=_compute_skippable(lesson.theory_skips_percentage, THEORY_SKIPS_THRESHOLD),
        practice_skippable=_compute_skippable(lesson.practice_skips_percentage, PRACTICE_SKIPS_THRESHOLD),
    )
