import uuid
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.core.time import BISHKEK_TZ
from manashelper.modules.schedule.application.campus import CampusQuery
from manashelper.modules.schedule.application.course import CourseNotFoundError, CourseQuery
from manashelper.modules.schedule.application.course_level import CourseLevel
from manashelper.modules.schedule.application.free_time import FreeTimeQuery, TooManyCoursesError
from manashelper.modules.schedule.application.schedule import ScheduleQuery
from manashelper.modules.schedule.application.subject_timetable import SubjectTimetableQuery
from manashelper.modules.schedule.application.use_cases import sync_timetable as sync_module
from manashelper.modules.schedule.application.use_cases.sync_room_catalog import SyncRoomCatalogUseCase
from manashelper.modules.schedule.application.use_cases.sync_timetable import SyncTimetableUseCase
from manashelper.modules.schedule.infrastructure.models.course import Course
from manashelper.modules.schedule.infrastructure.models.department import Department
from manashelper.modules.schedule.infrastructure.models.faculty import Faculty
from manashelper.modules.schedule.infrastructure.models.lesson import Lesson
from manashelper.modules.schedule.infrastructure.models.lesson_item import LessonItem
from manashelper.modules.schedule.infrastructure.models.room import Room
from manashelper.modules.schedule.infrastructure.repositories.course import CourseRepository
from manashelper.modules.schedule.infrastructure.repositories.course_tracking import CourseTrackingRepository
from manashelper.modules.schedule.infrastructure.repositories.lesson import LessonRepository
from manashelper.modules.schedule.infrastructure.repositories.lesson_history import LessonHistoryRepository
from manashelper.modules.schedule.infrastructure.repositories.lesson_item import LessonItemRepository
from manashelper.modules.schedule.infrastructure.repositories.room import RoomRepository
from manashelper.modules.schedule.infrastructure.timetable_parser import ScrapedLessonSlot, ScrapedTimeSlot
from manashelper.modules.users.infrastructure.models.user import User

USER_ID = 993_101
ROOM_A, ROOM_B = "ZZQA 101", "ZZQA 202"
TEACHER = "Zzqa ÖĞRETMEN"


class _FakeClient:
    def __init__(self, room_html: str = "") -> None:
        self.room_html = room_html

    async def fetch_timetable_html(self, course_id: int) -> str:
        return "<irrelevant/>"

    async def fetch_room_catalog_html(self) -> str:
        return self.room_html


def _slot(weekday: int, time_range: str, *lessons: ScrapedLessonSlot) -> ScrapedTimeSlot:
    return ScrapedTimeSlot(weekday=weekday, time_range=time_range, lessons=list(lessons))


def _lesson(code: str, name: str, room: str = ROOM_A, teacher: str = TEACHER) -> ScrapedLessonSlot:
    return ScrapedLessonSlot(lesson_code=code, lesson_name=name, teacher=teacher, room=room)


async def _make_courses(session: AsyncSession, *course_ids: int) -> list[Course]:
    faculty = Faculty(id=uuid.uuid4(), name="ZZQA faculty")
    department = Department(id=uuid.uuid4(), name="ZZQA department", faculty=faculty)
    courses = [
        Course(id=course_id, number=index, department=department) for index, course_id in enumerate(course_ids, 1)
    ]
    session.add_all(courses)
    await session.flush()
    return courses


async def _sync(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch, course_id: int, slots: list[ScrapedTimeSlot], title: str
) -> list[object]:
    monkeypatch.setattr(sync_module, "parse_timetable_page", lambda html: slots)
    monkeypatch.setattr(sync_module, "parse_timetable_title", lambda html: title)
    use_case = SyncTimetableUseCase(
        _FakeClient(),  # type: ignore[arg-type]
        LessonRepository(session),
        LessonHistoryRepository(session),
        CourseRepository(session),
    )
    changes = await use_case.execute(course_id)
    await session.flush()
    return list(changes)


def _campus(session: AsyncSession) -> CampusQuery:
    return CampusQuery(LessonRepository(session), LessonItemRepository(session), RoomRepository(session))


async def test_sync_stores_items_backfills_silently_and_updates_level(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    (course,) = await _make_courses(session, 993_001)
    session.add(
        Lesson(
            id=uuid.uuid4(),
            course_id=course.id,
            weekday=1,
            time_range="8:00-8:45",
            content="BİL-501 İLERİ ALGORİTMA — Zzqa ÖĞRETMEN, ZZQA 101",
            normalized_content="",
        )
    )
    await session.flush()
    slots = [_slot(1, "8:00-8:45", _lesson("BİL-501", "İLERİ ALGORİTMA"))]

    changes = await _sync(session, monkeypatch, course.id, slots, "5 - sınıf LEE Bilgisayar Mühendisliği ABD")

    assert changes == []
    items = (await session.scalars(select(LessonItem).join(Lesson).where(Lesson.course_id == course.id))).all()
    assert [(item.code, item.room_key, item.teacher_key, item.subject_key) for item in items] == [
        ("BİL-501", "zzqa101", "zzqa ogretmen", "bil501")
    ]
    assert course.level == CourseLevel.MASTER.value

    moved = [_slot(1, "8:00-8:45", _lesson("BİL-501", "İLERİ ALGORİTMA", room=ROOM_B))]
    changes = await _sync(session, monkeypatch, course.id, moved, "5 - sınıf LEE Bilgisayar Mühendisliği ABD")
    assert len(changes) == 1
    items = (await session.scalars(select(LessonItem).join(Lesson).where(Lesson.course_id == course.id))).all()
    assert [item.room for item in items] == [ROOM_B]

    await _sync(session, monkeypatch, course.id, [], "5 - sınıf LEE Bilgisayar Mühendisliği ABD")
    assert (await session.scalars(select(LessonItem).join(Lesson).where(Lesson.course_id == course.id))).all() == []


async def test_room_catalog_sync_and_campus_queries(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    first, second = await _make_courses(session, 993_011, 993_012)
    await _sync(
        session,
        monkeypatch,
        first.id,
        [
            _slot(1, "8:00-8:45", _lesson("BİL-107(T)", "PROGRAMLAMA")),
            _slot(1, "8:55-9:40", _lesson("BİL-107(T)", "PROGRAMLAMA")),
            _slot(1, "13:30-14:15", _lesson("BİL-107.01", "(U) PROGRAMLAMA", room=ROOM_B)),
            _slot(2, "8:00-8:45", _lesson("Ayrılmış", "(Reserved)", room="", teacher="")),
        ],
        "1 - sınıf ZZQA",
    )
    await _sync(session, monkeypatch, second.id, [_slot(3, "9:50-10:35", _lesson("MAT-101", "MATEMATİK"))], "2 - sınıf")

    room_html = (
        '<select id="timetablebundle_dersplangenerator_room">'
        '<option value="993901">ZZQA-101 kapasitesi: 40</option>'
        '<option value="993902">ZZQA-OLD kapasitesi: 5</option></select>'
    )
    session.add(Room(id=993_902, name="stale", capacity=1, room_key="stale"))
    await session.flush()
    synced = await SyncRoomCatalogUseCase(_FakeClient(room_html), RoomRepository(session)).execute()  # type: ignore[arg-type]
    await session.flush()
    assert synced == 2
    assert (await session.get(Room, 993_902)).name == "ZZQA-OLD"  # type: ignore[union-attr]

    campus = _campus(session)
    periods = ("8:00-8:45", "8:55-9:40", "9:50-10:35", "13:30-14:15")
    busy = await campus.get_free_rooms(1, 0, periods)
    free_keys = {room.key for room in busy.rooms}
    assert "zzqa101" not in free_keys and "zzqa202" in free_keys
    later = await campus.get_free_rooms(1, 2, periods)
    room_a = next(room for room in later.rooms if room.key == "zzqa101")
    room_b = next(room for room in later.rooms if room.key == "zzqa202")
    assert (room_a.name, room_a.capacity, room_a.building, room_a.free_until_minutes) == ("ZZQA-101", 40, "ZZQA", None)
    assert room_b.free_until_minutes == 13 * 60 + 30 and room_b.capacity is None

    matches = await campus.search_rooms("zzqa-10")
    assert [(match.key, match.name) for match in matches] == [("zzqa101", "ZZQA-101")]
    room = await campus.get_room("zzqa101")
    assert room is not None and room[0].capacity == 40
    assert {(entry.weekday, entry.time_range) for entry in room[1]} == {
        (1, "8:00-8:45"),
        (1, "8:55-9:40"),
        (3, "9:50-10:35"),
    }

    teachers = await campus.search_teachers("zzqa ogret")
    assert [match.name for match in teachers] == [TEACHER]
    teacher = await campus.get_teacher(teachers[0].key)
    assert teacher is not None and len(teacher[1]) == 4
    assert {entry.department_name for entry in teacher[1]} == {"ZZQA department"}


async def test_free_time_personal_now_next_and_subject_weeks(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = await _make_courses(session, 993_021, 993_022)
    await _sync(
        session,
        monkeypatch,
        first.id,
        [
            _slot(1, "8:00-8:45", _lesson("BİL-107(T)", "PROGRAMLAMA")),
            _slot(1, "8:55-9:40", _lesson("BİL-107(T)", "PROGRAMLAMA")),
            _slot(2, "10:45-11:30", _lesson("BİL-107.01", "(U) PROGRAMLAMA (Uygulama)", room=ROOM_B)),
        ],
        "1 - sınıf",
    )
    await _sync(session, monkeypatch, second.id, [_slot(1, "9:50-10:35", _lesson("MAT-101", "MATEMATİK"))], "2 - sınıf")

    free_time = FreeTimeQuery(CourseRepository(session), LessonRepository(session))
    result = await free_time.execute([first.id, second.id, first.id])
    assert [course.id for course in result.courses] == [first.id, second.id]
    monday = next(day for day in result.days if day.weekday == 1)
    assert all(window.start_minutes >= 10 * 60 + 35 for window in monday.windows)
    with pytest.raises(CourseNotFoundError):
        await free_time.execute([first.id, 993_099])
    with pytest.raises(TooManyCoursesError):
        await free_time.execute(list(range(1, 10)))

    user = User(id=USER_ID, full_name="ZZQA", locale="ru")
    session.add(user)
    await session.flush()
    tracking = CourseTrackingRepository(session)
    loaded = await tracking.get_with_tracked_courses(USER_ID)
    assert loaded is not None
    loaded.tracked_courses.append(first)
    await session.flush()

    schedule = ScheduleQuery(LessonRepository(session), tracking)
    now_next = await schedule.get_now_next(USER_ID, datetime(2026, 11, 9, 8, 50, tzinfo=BISHKEK_TZ))
    assert now_next.current is not None and now_next.current.time_ranges == ("8:00-8:45", "8:55-9:40")
    assert now_next.upcoming is not None and now_next.upcoming.weekday == 2

    weeks = await SubjectTimetableQuery(schedule).weekly_by_subject(USER_ID)
    assert (weeks["bil107"].theory_hours, weeks["bil107"].practice_hours) == (2, 1)
    assert await SubjectTimetableQuery(schedule).weekly_by_subject(USER_ID + 1) == {}

    courses = await CourseQuery(CourseRepository(session), tracking).get_tracked_courses(USER_ID)
    assert [course.level for course in courses] == [CourseLevel.BACHELOR]
