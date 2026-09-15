from aiogram.utils.i18n import gettext as _
from aiogram.utils.i18n import ngettext

from manashelper.services.obis import LessonAttendanceModel, LessonExamsModel
from manashelper.services.obis_notification import ExamGradeChange, LessonSkipChange, SkipType


def format_exam_grades(lessons: list[LessonExamsModel]) -> str:
    if not lessons:
        return _("You don't have any exam grades.")

    blocks = []
    for lesson in lessons:
        lines = [f"<b>{lesson.lesson_name} ({lesson.lesson_code})</b>"]
        for exam in lesson.exams:
            score = exam.score if exam.score is not None else "-"
            lines.append(f" - {exam.name}: {score}")
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def format_attendance(lessons: list[LessonAttendanceModel]) -> str:
    if not lessons:
        return _("You don't have any subjects.")

    blocks = []
    for lesson in lessons:
        theory_skips = lesson.theory_skippable
        practice_skips = lesson.practice_skippable

        name = f"<b>{lesson.lesson_name}</b>"
        if theory_skips == 0 or practice_skips == 0:
            name = f"❗ {name}"
        elif (theory_skips is not None and theory_skips <= 1) or (practice_skips is not None and practice_skips <= 1):
            name = f"⚠️ {name}"

        block = "\n".join(
            [
                name,
                _format_skips_line(_("Theory"), lesson.theory_skips_percentage, theory_skips),
                _format_skips_line(_("Practice"), lesson.practice_skips_percentage, practice_skips),
            ]
        )
        blocks.append(block)

    return "\n\n".join(blocks)


def _format_skips_line(label: str, percentage: float | None, skippable: int | None) -> str:
    line = f"{label}: {_format_float(percentage)}%"
    if skippable is None:
        return line
    left = ngettext("{count} skip left", "{count} skips left", skippable).format(count=skippable)
    return f"{line} ({left})"


def _format_float(value: float | None) -> str:
    if value is None:
        return "-"
    text = f"{value}".rstrip("0").rstrip(".")
    return text or "0"


def format_exam_grade_change(change: ExamGradeChange) -> str:
    lesson = change.lesson_name or _("Subject")
    exam = change.exam_name or _("Exam")
    return _("🔔 New grade for the subject «{lesson}»\n{exam}: {score}").format(
        lesson=lesson, exam=exam, score=change.score
    )


def format_lesson_skip_change(change: LessonSkipChange) -> str:
    skip_type_label = _("theory") if change.skip_type is SkipType.THEORY else _("practice")
    lines = [
        _("⚠️ A skip was recorded for the subject «{lesson}» ({skip_type})").format(
            lesson=change.lesson_name, skip_type=skip_type_label
        ),
        _("Missed: {percent}%").format(percent=_format_float(change.skips_percentage)),
    ]
    if change.skippable is not None:
        lines.append(
            ngettext("You have {count} skip left", "You have {count} skips left", change.skippable).format(
                count=change.skippable
            )
        )
    return "\n".join(lines)
