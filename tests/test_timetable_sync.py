import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import Course, Department, Faculty, Lesson, LessonHistory
from manashelper.repositories.lesson_history_repository import LessonHistoryRepository
from manashelper.repositories.lesson_repository import LessonRepository
from manashelper.scraping.timetable_parser import ScrapedLessonSlot, ScrapedTimeSlot
from manashelper.services import timetable_sync
from manashelper.services.timetable_sync import TimetableSyncService


class _FakeTimetableClient:
    async def fetch_timetable_html(self, course_id: int) -> str:
        return "<irrelevant/>"


async def _make_course(session: AsyncSession, course_id: int) -> Course:
    faculty = Faculty(id=uuid.uuid4(), name="Тестовый факультет")
    session.add(faculty)
    await session.flush()

    department = Department(id=uuid.uuid4(), name="Тестовое направление", faculty_id=faculty.id)
    session.add(department)
    await session.flush()

    course = Course(id=course_id, number=1, department_id=department.id)
    session.add(course)
    await session.flush()
    return course


async def test_synchronize_course_timetable_updates_content_and_records_history(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    course = await _make_course(session, 300_001)
    session.add(
        Lesson(
            id=uuid.uuid4(),
            course_id=course.id,
            weekday=1,
            time_range="09:00-09:50",
            content="Eski ders — Eski Hoca, 100",
            normalized_content="eski ders — eski hoca, 100",
        )
    )
    await session.flush()

    monkeypatch.setattr(
        timetable_sync,
        "parse_timetable_page",
        lambda html: [
            ScrapedTimeSlot(
                weekday=1,
                time_range="09:00-09:50",
                lessons=[
                    ScrapedLessonSlot(
                        lesson_code=None,
                        lesson_name="Yazılım Mühendisliğine Giriş",
                        teacher="Öğretmen",
                        room="101",
                    )
                ],
            )
        ],
    )

    service = TimetableSyncService(_FakeTimetableClient(), LessonRepository(session), LessonHistoryRepository(session))
    changes = await service.synchronize_course_timetable(course.id)
    await session.flush()

    assert len(changes) == 1
    assert changes[0].previous_content == "Eski ders — Eski Hoca, 100"
    assert changes[0].new_content == "Yazılım Mühendisliğine Giriş — Öğretmen, 101"

    result = await session.execute(select(Lesson).where(Lesson.course_id == course.id))
    lesson = result.scalar_one()
    assert lesson.content == "Yazılım Mühendisliğine Giriş — Öğretmen, 101"
    assert lesson.normalized_content == "yazilim muhendisligine giris — ogretmen, 101"

    history_result = await session.execute(select(LessonHistory).where(LessonHistory.course_id == course.id))
    history_entries = history_result.scalars().all()
    assert len(history_entries) == 1
    assert history_entries[0].previous_content == "Eski ders — Eski Hoca, 100"
    assert history_entries[0].new_content == "Yazılım Mühendisliğine Giriş — Öğretmen, 101"


async def test_synchronize_course_timetable_first_sync_creates_no_history(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    course = await _make_course(session, 300_002)

    monkeypatch.setattr(
        timetable_sync,
        "parse_timetable_page",
        lambda html: [
            ScrapedTimeSlot(
                weekday=2,
                time_range="10:00-10:50",
                lessons=[
                    ScrapedLessonSlot(lesson_code=None, lesson_name="Matematik", teacher="Hoca", room="102"),
                ],
            )
        ],
    )

    service = TimetableSyncService(_FakeTimetableClient(), LessonRepository(session), LessonHistoryRepository(session))
    changes = await service.synchronize_course_timetable(course.id)
    await session.flush()

    assert changes == []

    history_result = await session.execute(select(LessonHistory).where(LessonHistory.course_id == course.id))
    assert history_result.scalars().all() == []

    lesson_result = await session.execute(select(Lesson).where(Lesson.course_id == course.id))
    lesson = lesson_result.scalar_one()
    assert lesson.normalized_content == "matematik — hoca, 102"
