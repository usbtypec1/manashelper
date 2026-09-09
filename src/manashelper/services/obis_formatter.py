from manashelper.services.obis_service import LessonAttendanceModel, LessonExamsModel


def format_exam_grades(lessons: list[LessonExamsModel]) -> str:
    if not lessons:
        return "У вас нет оценок за экзамены."

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
        return "У вас нет предметов."

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
                _format_skips_line("Теория", lesson.theory_skips_percentage, theory_skips),
                _format_skips_line("Практика", lesson.practice_skips_percentage, practice_skips),
            ]
        )
        blocks.append(block)

    return "\n\n".join(blocks)


def _format_skips_line(label: str, percentage: float | None, skippable: int | None) -> str:
    line = f"{label}: {_format_float(percentage)}%"
    if skippable is None:
        return line
    return f"{line} (осталось {skippable} {_inflect_skips(skippable)})"


def _format_float(value: float | None) -> str:
    if value is None:
        return "-"
    text = f"{value}".rstrip("0").rstrip(".")
    return text or "0"


def _inflect_skips(count: int) -> str:
    count = abs(count)
    if count % 10 == 1 and count % 100 != 11:
        return "пропуск"
    if count % 10 in (2, 3, 4) and not (12 <= count % 100 <= 14):
        return "пропуска"
    return "пропусков"
