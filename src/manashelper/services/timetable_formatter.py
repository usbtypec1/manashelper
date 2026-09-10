from manashelper.services.timetable_sync_service import LessonChange

WEEKDAY_LABELS = {1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт"}


def format_lesson_changes(changes: list[LessonChange]) -> str:
    lines = ["🔔 Изменения в расписании:"]
    for change in changes:
        day = WEEKDAY_LABELS.get(change.weekday, "?")
        if change.previous_content is None:
            lines.append(f"➕ {day} {change.time_range}: {change.new_content}")
        elif change.new_content is None:
            lines.append(f"➖ {day} {change.time_range}: {change.previous_content} (отменено)")
        else:
            lines.append(f"✏️ {day} {change.time_range}: {change.previous_content} → {change.new_content}")
    return "\n".join(lines)
