import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.schedule.application.course import CourseNotFoundError, CourseService, UserNotFoundError
from manashelper.modules.schedule.infrastructure.models.course import Course
from manashelper.modules.schedule.infrastructure.models.department import Department
from manashelper.modules.schedule.infrastructure.models.faculty import Faculty
from manashelper.modules.schedule.infrastructure.repositories.course_repository import CourseRepository
from manashelper.modules.schedule.infrastructure.repositories.course_tracking_repository import CourseTrackingRepository
from manashelper.modules.users.infrastructure.user import User


async def _make_department(session: AsyncSession) -> Department:
    faculty = Faculty(id=uuid.uuid4(), name="Тестовый факультет")
    session.add(faculty)
    await session.flush()

    department = Department(id=uuid.uuid4(), name="Тестовое направление", faculty_id=faculty.id)
    session.add(department)
    await session.flush()
    return department


async def test_get_courses_by_department_marks_tracked_courses(session: AsyncSession) -> None:
    department = await _make_department(session)
    course_a = Course(id=100_001, number=1, department_id=department.id)
    course_b = Course(id=100_002, number=2, department_id=department.id)
    user = User(id=900_001, full_name="Test User", username=None)
    user.tracked_courses.append(course_a)
    session.add_all([course_a, course_b, user])
    await session.flush()

    service = CourseService(CourseRepository(session), CourseTrackingRepository(session))
    summaries = {s.id: s for s in await service.get_courses_by_department(department.id, user.id)}

    assert summaries[course_a.id].is_tracked is True
    assert summaries[course_b.id].is_tracked is False


async def test_toggle_tracked_course_adds_then_removes(session: AsyncSession) -> None:
    department = await _make_department(session)
    course = Course(id=100_003, number=1, department_id=department.id)
    user = User(id=900_002, full_name="Test User", username=None)
    session.add_all([course, user])
    await session.flush()

    service = CourseService(CourseRepository(session), CourseTrackingRepository(session))

    summaries = await service.toggle_tracked_course(course.id, user.id)
    assert next(s for s in summaries if s.id == course.id).is_tracked is True

    summaries = await service.toggle_tracked_course(course.id, user.id)
    assert next(s for s in summaries if s.id == course.id).is_tracked is False


async def test_toggle_tracked_course_raises_when_course_missing(session: AsyncSession) -> None:
    user = User(id=900_003, full_name="Test User", username=None)
    session.add(user)
    await session.flush()

    service = CourseService(CourseRepository(session), CourseTrackingRepository(session))

    with pytest.raises(CourseNotFoundError):
        await service.toggle_tracked_course(999_999, user.id)


async def test_toggle_tracked_course_raises_when_user_missing(session: AsyncSession) -> None:
    department = await _make_department(session)
    course = Course(id=100_004, number=1, department_id=department.id)
    session.add(course)
    await session.flush()

    service = CourseService(CourseRepository(session), CourseTrackingRepository(session))

    with pytest.raises(UserNotFoundError):
        await service.toggle_tracked_course(course.id, 999_999)
