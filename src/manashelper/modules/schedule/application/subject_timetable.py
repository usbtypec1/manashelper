"""Weekly timetable of each subject a user studies, keyed by course code for other features such as OBIS."""

import re
from dataclasses import dataclass

from manashelper.modules.schedule.application.course import UserNotFoundError
from manashelper.modules.schedule.application.lesson_items import LessonKind, lesson_kind, subject_key
from manashelper.modules.schedule.application.schedule import NoTrackedCoursesError, ScheduleQuery
from manashelper.modules.schedule.application.time_ranges import MAX_GAP_MINUTES_TO_GROUP
from manashelper.modules.schedule.application.timetable_entries import TimetableEntry

_SECTION_PATTERN = re.compile(r"\.(\d+)")


@dataclass(frozen=True, slots=True)
class SubjectSession:
    weekday: int
    start_minutes: int
    end_minutes: int
    kind: LessonKind
    section: str | None


@dataclass(frozen=True, slots=True)
class SubjectWeek:
    theory_hours: int
    practice_hours: int
    sessions: tuple[SubjectSession, ...]


def section_of(code: str | None) -> str | None:
    match = _SECTION_PATTERN.search(code or "")
    return match.group(1) if match else None


def _weekly_hours(slots: list[tuple[str | None, int, str]]) -> int:
    """Academic hours a single student attends: shared slots plus the busiest section (.01/.02 alternate)."""
    shared = {(weekday, time_range) for section, weekday, time_range in slots if section is None}
    sections: dict[str, set[tuple[int, str]]] = {}
    for section, weekday, time_range in slots:
        if section is not None:
            sections.setdefault(section, set()).add((weekday, time_range))
    return len(shared) + max((len(section_slots - shared) for section_slots in sections.values()), default=0)


def build_subject_weeks(entries: list[TimetableEntry]) -> dict[str, SubjectWeek]:
    grouped: dict[str, list[tuple[TimetableEntry, LessonKind, str | None]]] = {}
    for entry in entries:
        key = subject_key(entry.code)
        if key is not None:
            grouped.setdefault(key, []).append((entry, lesson_kind(entry.code, entry.name), section_of(entry.code)))

    weeks: dict[str, SubjectWeek] = {}
    for key, rows in grouped.items():
        sessions: list[SubjectSession] = []
        seen: set[tuple[int, str, LessonKind, str | None]] = set()
        for entry, kind, section in sorted(rows, key=lambda row: (row[0].weekday, row[0].start_minutes)):
            identity = (entry.weekday, entry.time_range, kind, section)
            if identity in seen:
                continue
            seen.add(identity)
            previous = next(
                (
                    index
                    for index in range(len(sessions) - 1, -1, -1)
                    if sessions[index].weekday == entry.weekday
                    and sessions[index].kind == kind
                    and sessions[index].section == section
                ),
                None,
            )
            if (
                previous is not None
                and entry.start_minutes - sessions[previous].end_minutes <= MAX_GAP_MINUTES_TO_GROUP
            ):
                session = sessions[previous]
                sessions[previous] = SubjectSession(
                    session.weekday, session.start_minutes, entry.end_minutes, session.kind, session.section
                )
            else:
                sessions.append(SubjectSession(entry.weekday, entry.start_minutes, entry.end_minutes, kind, section))

        def hours(kind: LessonKind, rows: list[tuple[TimetableEntry, LessonKind, str | None]] = rows) -> int:
            return _weekly_hours(
                [(section, entry.weekday, entry.time_range) for entry, k, section in rows if k == kind]
            )

        weeks[key] = SubjectWeek(
            theory_hours=hours(LessonKind.THEORY),
            practice_hours=hours(LessonKind.PRACTICE),
            sessions=tuple(sorted(sessions, key=lambda session: (session.weekday, session.start_minutes))),
        )
    return weeks


@dataclass(frozen=True, slots=True)
class SubjectTimetableQuery:
    schedule_query: ScheduleQuery

    async def weekly_by_subject(self, user_id: int) -> dict[str, SubjectWeek]:
        """Empty when the user is unknown or tracks no courses, so callers can degrade gracefully."""
        try:
            entries = await self.schedule_query.get_user_entries(user_id)
        except (UserNotFoundError, NoTrackedCoursesError):
            return {}
        return build_subject_weeks(entries)
