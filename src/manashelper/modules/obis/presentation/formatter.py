from collections.abc import Iterator, Mapping

from aiogram.utils.i18n import gettext as _
from aiogram.utils.i18n import ngettext

from manashelper.localization.weekdays import weekday_abbr
from manashelper.modules.obis.application.models import LessonAttendanceModel, LessonExamsModel
from manashelper.modules.obis.application.notification import ExamGradeChange, LessonSkipChange, SkipType
from manashelper.modules.schedule.application.lesson_items import LessonKind, subject_key
from manashelper.modules.schedule.application.subject_timetable import SubjectSession, SubjectWeek
from manashelper.modules.schedule.application.time_ranges import format_minutes

SUBJECTS_PER_PAGE = 2
MAX_PAGE_BODY_CHARS = 1600
MAX_PAGE_BODY_LINES = 10


def _split_block(block: str) -> Iterator[str]:
    lines: list[str] = []
    for line in block.split("\n"):
        for offset in range(0, max(1, len(line)), MAX_PAGE_BODY_CHARS):
            part = line[offset : offset + MAX_PAGE_BODY_CHARS]
            candidate = "\n".join([*lines, part])
            if lines and (len(candidate) > MAX_PAGE_BODY_CHARS or len(lines) >= MAX_PAGE_BODY_LINES):
                yield "\n".join(lines)
                lines = []
            lines.append(part)
    if lines:
        yield "\n".join(lines)


def _build_pages(title: str, blocks: list[str], empty_text: str) -> list[str]:
    if not blocks:
        return [f"{title}\n\n{empty_text}"]
    bodies: list[str] = []
    current: list[str] = []
    for block in blocks:
        for chunk in _split_block(block):
            candidate = "\n\n".join([*current, chunk])
            if current and (
                len(current) >= SUBJECTS_PER_PAGE
                or len(candidate) > MAX_PAGE_BODY_CHARS
                or len(candidate.split("\n")) > MAX_PAGE_BODY_LINES
            ):
                bodies.append("\n\n".join(current))
                current = []
            current.append(chunk)
    if current:
        bodies.append("\n\n".join(current))
    pages = []
    for index, body in enumerate(bodies, start=1):
        text = f"{title}\n\n{body}"
        if len(bodies) > 1:
            text += "\n\n" + _("obis.page_indicator").format(page=index, total=len(bodies))
        pages.append(text)
    return pages


def format_exam_grades_pages(lessons: list[LessonExamsModel]) -> list[str]:
    blocks = []
    for lesson in lessons:
        name = lesson.lesson_name or _("obis.subject")
        title = f"{name} ({lesson.lesson_code})" if lesson.lesson_code else name
        lines = [title]
        for exam in lesson.exams:
            score = exam.score if exam.score is not None else "-"
            lines.append(f"• {exam.name or _('obis.exam')}: {score}")
        blocks.append("\n".join(lines))
    return _build_pages(_("menu.grades"), blocks, _("obis.no_grades"))


def _format_session(session: SubjectSession) -> str:
    kind = _("obis.kind_theory") if session.kind == LessonKind.THEORY else _("obis.kind_practice")
    if session.section is not None:
        kind = f"{kind} .{session.section}"
    span = f"{format_minutes(session.start_minutes)}–{format_minutes(session.end_minutes)}"
    return f"{weekday_abbr(session.weekday)} {span} ({kind})"


def format_subject_week(week: SubjectWeek) -> str:
    """Plain-text timetable line under a subject's attendance (OBIS pages use parse_mode=None)."""
    sessions = ", ".join(_format_session(session) for session in week.sessions)
    hours = _("obis.weekly_hours").format(theory=week.theory_hours, practice=week.practice_hours)
    return f"🗓 {sessions} · {hours}"


def format_attendance_pages(
    lessons: list[LessonAttendanceModel], weeks: Mapping[str, SubjectWeek] | None = None
) -> list[str]:
    """Attendance pages; ``weeks`` (by schedule subject key) adds each subject's weekly timetable when known."""
    blocks = []
    for lesson in lessons:
        theory_skips = lesson.theory_skippable
        practice_skips = lesson.practice_skippable

        name = lesson.lesson_name
        if theory_skips == 0 or practice_skips == 0:
            name = f"❗ {name}"
        elif (theory_skips is not None and theory_skips <= 1) or (practice_skips is not None and practice_skips <= 1):
            name = f"⚠️ {name}"

        lines = [
            name,
            _format_skips_line(_("obis.theory"), lesson.theory_skips_percentage, theory_skips),
            _format_skips_line(_("obis.practice"), lesson.practice_skips_percentage, practice_skips),
        ]
        key = subject_key(lesson.lesson_code)
        week = weeks.get(key) if weeks is not None and key is not None else None
        if week is not None and week.sessions:
            lines.append(format_subject_week(week))
        blocks.append("\n".join(lines))

    return _build_pages(_("menu.attendance"), blocks, _("obis.no_subjects"))


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
