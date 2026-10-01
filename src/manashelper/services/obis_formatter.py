from aiogram.types import InputRichBlockParagraph, InputRichBlockSectionHeading, InputRichBlockUnion
from aiogram.utils.i18n import gettext as _
from aiogram.utils.i18n import ngettext

from manashelper.services.obis import LessonAttendanceModel, LessonExamsModel
from manashelper.services.obis_notification import ExamGradeChange, LessonSkipChange, SkipType


def build_exam_grade_blocks(lesson: LessonExamsModel) -> list[InputRichBlockUnion]:
    name = lesson.lesson_name or _("obis.subject")
    title = f"{name} ({lesson.lesson_code})" if lesson.lesson_code else name
    blocks: list[InputRichBlockUnion] = [InputRichBlockSectionHeading(size=3, text=title)]
    if lesson.exams:
        lines = [
            f"{exam.name or _('obis.exam')}: {exam.score if exam.score is not None else '-'}" for exam in lesson.exams
        ]
        blocks.append(InputRichBlockParagraph(text="\n".join(lines)))
    return blocks


def build_attendance_blocks(lesson: LessonAttendanceModel) -> list[InputRichBlockUnion]:
    name = lesson.lesson_name
    if lesson.theory_skippable == 0 or lesson.practice_skippable == 0:
        name = f"❗ {name}"
    elif any(count is not None and count <= 1 for count in (lesson.theory_skippable, lesson.practice_skippable)):
        name = f"⚠️ {name}"
    return [
        InputRichBlockSectionHeading(size=3, text=name),
        InputRichBlockParagraph(
            text="\n".join(
                [
                    _format_skips_line(_("obis.theory"), lesson.theory_skips_percentage, lesson.theory_skippable),
                    _format_skips_line(_("obis.practice"), lesson.practice_skips_percentage, lesson.practice_skippable),
                ]
            )
        ),
    ]


def format_exam_grades(lessons: list[LessonExamsModel]) -> str:
    if not lessons:
        return _("obis.no_grades")

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
        return _("obis.no_subjects")

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
                _format_skips_line(_("obis.theory"), lesson.theory_skips_percentage, theory_skips),
                _format_skips_line(_("obis.practice"), lesson.practice_skips_percentage, practice_skips),
            ]
        )
        blocks.append(block)

    return "\n\n".join(blocks)


def _format_skips_line(label: str, percentage: float | None, skippable: int | None) -> str:
    line = f"{label}: {_format_float(percentage)}%"
    if skippable is None:
        return line
    left = ngettext("obis.skips_left.one", "obis.skips_left.many", skippable).format(count=skippable)
    return f"{line} ({left})"


def _format_float(value: float | None) -> str:
    if value is None:
        return "-"
    text = f"{value}".rstrip("0").rstrip(".")
    return text or "0"


def format_exam_grade_change(change: ExamGradeChange) -> str:
    lesson = change.lesson_name or _("obis.subject")
    exam = change.exam_name or _("obis.exam")
    return _("obis.new_grade").format(lesson=lesson, exam=exam, score=change.score)


def format_lesson_skip_change(change: LessonSkipChange) -> str:
    skip_type_label = _("obis.theory_lower") if change.skip_type is SkipType.THEORY else _("obis.practice_lower")
    lines = [
        _("obis.skip_recorded").format(lesson=change.lesson_name, skip_type=skip_type_label),
        _("obis.missed_percentage").format(percent=_format_float(change.skips_percentage)),
    ]
    if change.skippable is not None:
        lines.append(
            ngettext("obis.remaining_skips.one", "obis.remaining_skips.many", change.skippable).format(
                count=change.skippable
            )
        )
    return "\n".join(lines)
