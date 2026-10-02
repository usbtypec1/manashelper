import unicodedata

from manashelper.services.eders_models import ActivityKind, EdersActivity, EdersCourse, EdersGrade, EdersSnapshot


def _matches(query: str, *fields: str) -> bool:
    text = unicodedata.normalize("NFKC", " ".join(fields)).casefold()
    return all(word in text for word in unicodedata.normalize("NFKC", query).casefold().split())


def catalog_courses(snapshot: EdersSnapshot) -> list[EdersCourse]:
    courses = {course.id: course for course in snapshot.courses}
    courses.update({item.course.id: item.course for item in snapshot.activities})
    courses.update({item.course.id: item.course for item in snapshot.grades})
    return sorted(courses.values(), key=lambda course: (course.name.casefold(), course.id))


def find_materials(snapshot: EdersSnapshot, course_id: int = 0, query: str = "") -> list[EdersActivity]:
    return sorted(
        (
            item
            for item in snapshot.activities
            if item.kind != ActivityKind.GRADE
            and (not course_id or item.course.id == course_id)
            and _matches(query, item.name, item.section, item.course.name)
        ),
        key=lambda item: (item.course.name.casefold(), item.section.casefold(), item.name.casefold(), item.id),
    )


def find_grades(snapshot: EdersSnapshot, course_id: int = 0) -> list[EdersGrade]:
    return sorted(
        (
            item
            for item in snapshot.grades
            if item.course.id not in snapshot.unavailable_grade_courses
            and (not course_id or item.course.id == course_id)
        ),
        key=lambda item: (item.course.name.casefold(), item.name.casefold(), item.id),
    )
