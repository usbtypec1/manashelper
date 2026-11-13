import re
from enum import StrEnum

# The site numbers graduate programmes as "5 - sınıf LEE ..." (master's) and "6 - sınıf LEE ..." (doctorate).
# Medicine also has genuine 5th and 6th years, so the number alone is not enough.
_GRADUATE_TITLE_PATTERN = re.compile(r"^\s*(\d+)\s*-\s*s[ıi]n[ıi]f\s+LEE\b", re.IGNORECASE)
MASTER_COURSE_NUMBER = 5
DOCTORATE_COURSE_NUMBER = 6


class CourseLevel(StrEnum):
    BACHELOR = "bachelor"
    MASTER = "master"
    DOCTORATE = "doctorate"


def course_level_from_title(title: str | None) -> CourseLevel | None:
    if title is None:
        return None
    match = _GRADUATE_TITLE_PATTERN.match(title)
    if match is None:
        return CourseLevel.BACHELOR
    number = int(match.group(1))
    if number == MASTER_COURSE_NUMBER:
        return CourseLevel.MASTER
    if number == DOCTORATE_COURSE_NUMBER:
        return CourseLevel.DOCTORATE
    return CourseLevel.BACHELOR


def parse_course_level(value: str) -> CourseLevel:
    try:
        return CourseLevel(value)
    except ValueError:
        return CourseLevel.BACHELOR
