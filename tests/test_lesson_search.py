import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import Course, Department, Faculty, Lesson
from manashelper.repositories.lesson_repository import LessonRepository
from manashelper.services.lesson_search import LessonSearchService
from manashelper.services.text_normalization import fold_turkish


async def _make_course(session: AsyncSession, course_id: int) -> Course:
    faculty = Faculty(id=uuid.uuid4(), name="Инженерный факультет")
    session.add(faculty)
    await session.flush()

    department = Department(id=uuid.uuid4(), name="Программная инженерия", faculty_id=faculty.id)
    session.add(department)
    await session.flush()

    course = Course(id=course_id, number=1, department_id=department.id)
    session.add(course)
    await session.flush()
    return course


async def test_search_matches_query_with_plain_latin_for_turkish_diacritics(session: AsyncSession) -> None:
    # The dev database keeps real timetable data from prior syncs, so the test content uses a made-up
    # subject name (still folding every Turkish diacritic) to guarantee it can't collide with a real one.
    course = await _make_course(session, 400_001)
    content = "Şğıöüç Deneme Dersi — Öğretmen, 101"
    session.add(
        Lesson(
            id=uuid.uuid4(),
            course_id=course.id,
            weekday=1,
            time_range="09:00-09:50",
            content=content,
            normalized_content=fold_turkish(content),
        )
    )
    await session.flush()

    service = LessonSearchService(LessonRepository(session))
    results = await service.search("sgiouc deneme")  # plain Latin for "Şğıöüç Deneme"

    assert len(results) == 1
    assert results[0].course_id == course.id
    assert results[0].course_number == 1
    assert results[0].faculty_name == "Инженерный факультет"
    assert results[0].department_name == "Программная инженерия"
    assert results[0].content == content
    assert results[0].time_ranges == ["09:00-09:50"]


async def test_search_groups_consecutive_periods_with_same_content(session: AsyncSession) -> None:
    course = await _make_course(session, 400_002)
    content = "Ğşışüöç Bloklu Dersi — Öğretmen, 102"
    session.add_all(
        [
            Lesson(
                id=uuid.uuid4(),
                course_id=course.id,
                weekday=1,
                time_range="13:30-14:15",
                content=content,
                normalized_content=fold_turkish(content),
            ),
            Lesson(
                id=uuid.uuid4(),
                course_id=course.id,
                weekday=1,
                time_range="14:25-15:10",
                content=content,
                normalized_content=fold_turkish(content),
            ),
        ]
    )
    await session.flush()

    service = LessonSearchService(LessonRepository(session))
    results = await service.search("bloklu")

    assert len(results) == 1
    assert results[0].time_ranges == ["13:30-14:15", "14:25-15:10"]


async def test_search_returns_nothing_for_unrelated_query(session: AsyncSession) -> None:
    course = await _make_course(session, 400_003)
    content = "Matematik — Hoca, 102"
    session.add(
        Lesson(
            id=uuid.uuid4(),
            course_id=course.id,
            weekday=1,
            time_range="10:00-10:50",
            content=content,
            normalized_content=fold_turkish(content),
        )
    )
    await session.flush()

    service = LessonSearchService(LessonRepository(session))
    results = await service.search("fizika")

    assert results == []
