from datetime import datetime

import pytest

from manashelper.core.time import BISHKEK_TZ
from manashelper.modules.schedule.application.campus import current_period, natural_sort_key, sort_periods
from manashelper.modules.schedule.application.course_level import CourseLevel, course_level_from_title
from manashelper.modules.schedule.application.free_time import free_windows
from manashelper.modules.schedule.application.lesson_items import (
    LessonItemModel,
    LessonKind,
    building_of,
    format_items,
    is_bookable_room,
    is_reserved,
    lesson_kind,
    parse_slot_content,
    room_key,
    subject_key,
    teacher_key,
)
from manashelper.modules.schedule.application.subject_timetable import build_subject_weeks, section_of
from manashelper.modules.schedule.application.timetable_entries import TimetableEntry, find_now_next, group_blocks
from manashelper.modules.schedule.infrastructure.timetable_parser import (
    TimetableParseError,
    parse_room_catalog,
    parse_timetable_title,
)

PERIODS = ("8:00-8:45", "8:55-9:40", "9:50-10:35", "10:45-11:30", "11:40-12:25", "13:30-14:15", "14:25-15:10")


def _entry(weekday: int, time_range: str, code: str = "BİL-107(T)", room: str = "MFFB-127") -> TimetableEntry:
    return TimetableEntry(
        weekday=weekday,
        time_range=time_range,
        code=code,
        name="PROGRAMLAMA DİLLERİ I",
        teacher="BAKIT ŞARŞEMBAYEV",
        room=room,
        department_name="Bilgisayar Mühendisliği",
        course_number=1,
        course_level=CourseLevel.BACHELOR,
    )


def test_slot_content_round_trips_through_structured_items() -> None:
    items = [
        LessonItemModel("BİL-107.01", "(U) PROGRAMLAMA — DİLLERİ I", "BAKIT ŞARŞEMBAYEV", "MFFB 525"),
        LessonItemModel(None, "Ayrılmış", "", ""),
    ]
    assert parse_slot_content(format_items(items)) == items


def test_lookup_keys_ignore_spelling_differences() -> None:
    assert room_key("MFFB 127") == room_key("MFFB-127") == room_key("mffb127") == "mffb127"
    assert room_key("İİBF A-205") == "iibfa205"
    assert teacher_key("  BAKIT   Şarşembayev ") == "bakit sarsembayev"
    assert subject_key("BİL-107.02") == subject_key("BIL-107(T)") == subject_key("bil 107") == "bil107"
    assert subject_key(None) is None and subject_key("(T)") is None


def test_lesson_kind_reserved_and_room_classification() -> None:
    assert lesson_kind("BİL-107.02", "(U) PROGRAMLAMA DİLLERİ I") == LessonKind.PRACTICE
    assert lesson_kind("UME-111.01", "FİZİK I (UYGULAMA)") == LessonKind.PRACTICE
    assert lesson_kind("MAT-171.01", "MATEMATİK I") == LessonKind.THEORY
    assert is_reserved(LessonItemModel("Ayrılmış", "(Reserved)", "", ""))
    assert not is_reserved(LessonItemModel("BİL-107", "Ayrılmış konu", "Hoca", "MFFB-127"))
    assert is_bookable_room("MFFB-127") and not is_bookable_room("GZKM-Online") and not is_bookable_room("")
    assert building_of("İİBF A-205") == "İİBF" and building_of("MFFB-127") == "MFFB"
    assert section_of("BİL-107.02 (U)") == "02" and section_of("BİL-107(T)") is None


@pytest.mark.parametrize(
    ("title", "level"),
    [
        ("1 - sınıf Bilgisayar Mühendisliği", CourseLevel.BACHELOR),
        ("5 - sınıf LEE Bilgisayar Mühendisliği ABD", CourseLevel.MASTER),
        ("6 - sınıf LEE Çevre Mühendisliği ABD", CourseLevel.DOCTORATE),
        ("6 - sınıf TIP", CourseLevel.BACHELOR),
        (None, None),
    ],
)
def test_course_level_comes_from_page_heading(title: str | None, level: CourseLevel | None) -> None:
    assert course_level_from_title(title) == level


def test_parsers_read_heading_and_room_catalog() -> None:
    assert parse_timetable_title("<h3>\n 5 - sınıf LEE  Biyoloji ABD </h3>") == "5 - sınıf LEE Biyoloji ABD"
    assert parse_timetable_title("<p>none</p>") is None
    html = """
    <select id="timetablebundle_dersplangenerator_room">
      <option value="">Derslik seçiniz</option>
      <option value="633">MFFB-127 kapasitesi: 50</option>
      <option value="370">ENSB-GZKM-113  kapasitesi: 15</option>
    </select>"""
    rooms = parse_room_catalog(html)
    assert [(room.id, room.name, room.capacity) for room in rooms] == [
        (633, "MFFB-127", 50),
        (370, "ENSB-GZKM-113", 15),
    ]
    with pytest.raises(TimetableParseError):
        parse_room_catalog("<html></html>")


def test_periods_sorting_current_period_and_natural_order() -> None:
    periods = sort_periods(["10:45-11:30", "8:00-8:45", "9:50-10:35", "8:00-8:45"])
    assert periods == ("8:00-8:45", "9:50-10:35", "10:45-11:30")
    monday_break = datetime(2026, 11, 9, 9, 45, tzinfo=BISHKEK_TZ)
    assert current_period(periods, monday_break) == (1, 1)
    friday_evening = datetime(2026, 11, 13, 20, 0, tzinfo=BISHKEK_TZ)
    assert current_period(periods, friday_evening) == (1, 0)
    assert sorted(["MFFB-1012", "MFFB-127", "MFFB-13"], key=natural_sort_key) == ["MFFB-13", "MFFB-127", "MFFB-1012"]


def test_free_windows_merge_consecutive_periods_across_lunch() -> None:
    windows = free_windows(PERIODS, {"8:55-9:40", "14:25-15:10"})
    assert [(window.start_minutes, window.end_minutes, window.periods) for window in windows] == [
        (8 * 60, 8 * 60 + 45, 1),
        (9 * 60 + 50, 14 * 60 + 15, 4),
    ]
    assert free_windows(PERIODS, set(PERIODS)) == ()


def test_blocks_and_now_next_wrap_to_next_week() -> None:
    entries = [_entry(1, "8:00-8:45"), _entry(1, "8:55-9:40"), _entry(3, "13:30-14:15", room="MFFB-513")]
    blocks = group_blocks(entries)
    assert [(block.weekday, block.time_ranges) for block in blocks] == [
        (1, ("8:00-8:45", "8:55-9:40")),
        (3, ("13:30-14:15",)),
    ]

    during = find_now_next(entries, datetime(2026, 11, 9, 8, 30, tzinfo=BISHKEK_TZ))
    assert during.current == blocks[0] and during.upcoming == blocks[1] and not during.upcoming_is_today

    before_wednesday = find_now_next(entries, datetime(2026, 11, 11, 12, 0, tzinfo=BISHKEK_TZ))
    assert before_wednesday.current is None and before_wednesday.upcoming == blocks[1]
    assert before_wednesday.upcoming_is_today

    weekend = find_now_next(entries, datetime(2026, 11, 14, 12, 0, tzinfo=BISHKEK_TZ))
    assert weekend.current is None and weekend.upcoming == blocks[0]


def test_subject_weeks_count_one_section_and_merge_sessions() -> None:
    entries = [
        _entry(1, "8:00-8:45"),
        _entry(1, "8:55-9:40"),
        _entry(2, "10:45-11:30", code="BİL-107.01"),
        _entry(2, "11:40-12:25", code="BİL-107.01"),
        _entry(3, "10:45-11:30", code="BİL-107.02"),
        _entry(3, "11:40-12:25", code="BİL-107.02"),
    ]
    entries = [
        entry if "(T)" in (entry.code or "") else _with_name(entry, "(U) PROGRAMLAMA DİLLERİ I") for entry in entries
    ]
    week = build_subject_weeks(entries)["bil107"]
    assert (week.theory_hours, week.practice_hours) == (2, 2)
    assert [(session.weekday, session.kind, session.section) for session in week.sessions] == [
        (1, LessonKind.THEORY, None),
        (2, LessonKind.PRACTICE, "01"),
        (3, LessonKind.PRACTICE, "02"),
    ]
    assert week.sessions[0].end_minutes == 9 * 60 + 40


def _with_name(entry: TimetableEntry, name: str) -> TimetableEntry:
    return TimetableEntry(
        entry.weekday,
        entry.time_range,
        entry.code,
        name,
        entry.teacher,
        entry.room,
        entry.department_name,
        entry.course_number,
        entry.course_level,
    )
