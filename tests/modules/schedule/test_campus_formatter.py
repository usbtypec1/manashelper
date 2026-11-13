from datetime import datetime

import pytest

from manashelper.core.time import BISHKEK_TZ
from manashelper.modules.obis.application.models import LessonAttendanceModel
from manashelper.modules.obis.presentation.formatter import format_attendance_pages
from manashelper.modules.schedule.application.campus import FreeRoom, FreeRooms
from manashelper.modules.schedule.application.course_level import CourseLevel
from manashelper.modules.schedule.application.lesson_items import LessonKind
from manashelper.modules.schedule.application.subject_timetable import SubjectSession, SubjectWeek
from manashelper.modules.schedule.application.timetable_entries import TimetableEntry, find_now_next
from manashelper.modules.schedule.application.timetable_sync import LessonChange
from manashelper.modules.schedule.presentation.entries_formatter import (
    format_free_rooms,
    format_now_next,
    format_teacher,
)
from manashelper.modules.schedule.presentation.labels import course_label
from manashelper.modules.schedule.presentation.timetable_formatter import format_lesson_changes
from manashelper.platform.i18n.catalog import i18n

OLD = "BİL-107(T) PROGRAMLAMA — Hoca <A>, MFFB 127"
MOVED = "BİL-107(T) PROGRAMLAMA — Hoca <A>, MFFB 513"


@pytest.fixture(autouse=True)
def _en_locale():
    with i18n.context(), i18n.use_locale("en"):
        yield


def _entry(time_range: str, weekday: int = 1) -> TimetableEntry:
    return TimetableEntry(
        weekday=weekday,
        time_range=time_range,
        code="BİL-107(T)",
        name="PROGRAMLAMA & ALGORİTMA",
        teacher="BAKIT ŞARŞEMBAYEV",
        room="MFFB-127",
        department_name="Bilgisayar Mühendisliği",
        course_number=5,
        course_level=CourseLevel.MASTER,
    )


def test_course_label_names_graduate_programmes() -> None:
    assert course_label(3, CourseLevel.BACHELOR) == "Year 3"
    assert course_label(5, CourseLevel.MASTER) == "Master's"
    assert course_label(6, CourseLevel.DOCTORATE) == "PhD"
    with i18n.use_locale("ru"):
        assert course_label(5, CourseLevel.MASTER) == "Магистратура"


def test_room_move_is_one_merged_detailed_change() -> None:
    changes = [
        LessonChange(1, "8:00-8:45", OLD, MOVED),
        LessonChange(1, "8:55-9:40", OLD, MOVED),
        LessonChange(1, "13:30-14:15", None, "MAT-101 MATEMATİK — Hoca B, İİBF 127"),
    ]
    text = format_lesson_changes(changes)
    assert text.count("✏️") == 1 and "8:00–9:40" in text
    assert "🚪 Room: MFFB 127 → MFFB 513" in text
    assert "Teacher:" not in text and "Hoca &lt;A&gt;" not in text
    assert "➕ 13:30–14:15" in text and "<b>MAT-101 MATEMATİK</b>" in text


def test_replaced_lesson_keeps_full_before_and_after() -> None:
    text = format_lesson_changes([LessonChange(2, "8:00-8:45", OLD, "FİZ-101 FİZİK — Hoca <A>, MFFB 127")])
    assert "Room:" not in text
    assert "<b>BİL-107(T) PROGRAMLAMA</b>" in text and "<b>FİZ-101 FİZİK</b>" in text
    assert "Hoca &lt;A&gt; - MFFB 127" in text


def test_free_rooms_overview_and_building_list() -> None:
    result = FreeRooms(
        weekday=1,
        period=0,
        periods=("8:00-8:45",),
        rooms=(
            FreeRoom("mffb127", "MFFB-127", "MFFB", 50, 13 * 60 + 30),
            FreeRoom("mffb513", "MFFB-513", "MFFB", None, None),
            FreeRoom("iibf127", "İİBF-127", "İİBF", 60, None),
        ),
    )
    assert "Free rooms: 3" in format_free_rooms(result, "")
    building = format_free_rooms(result, "MFFB")
    assert "<b>MFFB-127</b> · 50 seats · until 13:30" in building
    assert "<b>MFFB-513</b> · until the end of the day" in building and "İİBF" not in building
    empty = FreeRooms(weekday=1, period=0, periods=("8:00-8:45",), rooms=())
    assert "No rooms are free" in format_free_rooms(empty, "")


def test_now_next_and_teacher_views_escape_and_label() -> None:
    entries = [_entry("8:00-8:45"), _entry("8:55-9:40"), _entry("13:30-14:15")]
    now = datetime(2026, 11, 9, 8, 10, tzinfo=BISHKEK_TZ)
    text = format_now_next(find_now_next(entries, now), now)
    assert "until 9:40" in text and "today at 13:30" in text
    assert "PROGRAMLAMA &amp; ALGORİTMA" in text and "Master's" not in text

    teacher = format_teacher("BAKIT <Ş>", entries, 1, find_now_next(entries, now), now)
    assert "BAKIT &lt;Ş&gt;" in teacher and "🔥 🕘 8:00–9:40" in teacher
    assert "Bilgisayar Mühendisliği, Master's" in teacher and "👨‍🏫" not in teacher.split("\n", 1)[1]


def test_attendance_shows_subject_timetable_when_known() -> None:
    lesson = LessonAttendanceModel("Programlama", "BİL-107", 12.5, 0.0, 2, 3)
    week = SubjectWeek(
        theory_hours=2,
        practice_hours=2,
        sessions=(
            SubjectSession(1, 8 * 60, 9 * 60 + 40, LessonKind.THEORY, None),
            SubjectSession(2, 10 * 60 + 45, 12 * 60 + 25, LessonKind.PRACTICE, "01"),
        ),
    )
    page = format_attendance_pages([lesson], {"bil107": week})[0]
    assert "🗓 Mon 8:00–9:40 (theory), Tue 10:45–12:25 (practice .01) · 2 h theory + 2 h practice per week" in page
    assert "🗓" not in format_attendance_pages([lesson])[0]
