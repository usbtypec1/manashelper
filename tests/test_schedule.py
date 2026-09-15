import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import Course, Department, Faculty, Lesson, User
from manashelper.repositories.lesson_repository import LessonRepository
from manashelper.repositories.user_repository import UserRepository
from manashelper.services.schedule import ScheduleService


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


async def test_has_lesson_during_lunch_true_when_lesson_overlaps_lunch_window(session: AsyncSession) -> None:
    course = await _make_course(session, 400_001)
    user = User(id=900_101, full_name="Test User", username=None)
    user.tracked_courses.append(course)
    session.add_all(
        [
            user,
            Lesson(
                id=uuid.uuid4(),
                course_id=course.id,
                weekday=1,
                time_range="13:00-13:50",
                content="Ders — Hoca, 101",
                normalized_content="ders — hoca, 101",
            ),
        ]
    )
    await session.flush()

    service = ScheduleService(LessonRepository(session), UserRepository(session))

    assert await service.has_lesson_during_lunch(user.id, weekday=1) is True


async def test_has_lesson_during_lunch_false_when_no_lesson_overlaps(session: AsyncSession) -> None:
    course = await _make_course(session, 400_002)
    user = User(id=900_102, full_name="Test User", username=None)
    user.tracked_courses.append(course)
    session.add_all(
        [
            user,
            Lesson(
                id=uuid.uuid4(),
                course_id=course.id,
                weekday=1,
                time_range="09:00-09:50",
                content="Ders — Hoca, 101",
                normalized_content="ders — hoca, 101",
            ),
        ]
    )
    await session.flush()

    service = ScheduleService(LessonRepository(session), UserRepository(session))

    assert await service.has_lesson_during_lunch(user.id, weekday=1) is False


async def test_has_lesson_during_lunch_false_when_lesson_is_on_a_different_weekday(session: AsyncSession) -> None:
    course = await _make_course(session, 400_003)
    user = User(id=900_103, full_name="Test User", username=None)
    user.tracked_courses.append(course)
    session.add_all(
        [
            user,
            Lesson(
                id=uuid.uuid4(),
                course_id=course.id,
                weekday=2,
                time_range="13:00-13:50",
                content="Ders — Hoca, 101",
                normalized_content="ders — hoca, 101",
            ),
        ]
    )
    await session.flush()

    service = ScheduleService(LessonRepository(session), UserRepository(session))

    assert await service.has_lesson_during_lunch(user.id, weekday=1) is False


async def test_has_lesson_during_lunch_false_when_user_has_no_tracked_courses(session: AsyncSession) -> None:
    user = User(id=900_104, full_name="Test User", username=None)
    session.add(user)
    await session.flush()

    service = ScheduleService(LessonRepository(session), UserRepository(session))

    assert await service.has_lesson_during_lunch(user.id, weekday=1) is False
