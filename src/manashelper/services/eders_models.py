from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from zoneinfo import ZoneInfo

BISHKEK_TZ = ZoneInfo("Asia/Bishkek")


class ActivityKind(StrEnum):
    ASSIGNMENT = "assign"
    QUIZ = "quiz"
    RESOURCE = "resource"
    LINK = "url"
    PAGE = "page"
    BOOK = "book"
    FOLDER = "folder"
    LESSON = "lesson"
    H5P = "h5pactivity"
    LABEL = "label"
    GRADE = "grade"


class SubmissionStatus(StrEnum):
    UNKNOWN = "unknown"
    NOT_SUBMITTED = "not_submitted"
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_PROGRESS = "in_progress"


class GradingStatus(StrEnum):
    UNKNOWN = "unknown"
    NOT_GRADED = "not_graded"
    GRADED = "graded"


class DeadlineFilter(StrEnum):
    ALL = "all"
    NEXT_SEVEN_DAYS = "week"
    AVAILABLE = "available"
    AWAITING_GRADE = "awaiting_grade"
    UNKNOWN_DEADLINE = "unknown_deadline"
    NOT_SUBMITTED = "not_submitted"
    SUBMITTED = "submitted"
    GRADED = "graded"
    UNKNOWN_STATUS = "unknown_status"


class EdersCatalogView(StrEnum):
    MATERIAL_COURSES = "mc"
    MATERIALS = "m"
    GRADE_COURSES = "gc"
    GRADES = "g"
    FEEDBACK = "f"


@dataclass(frozen=True, slots=True)
class ActivityDate:
    # A missing instant is deliberate: a display date without an account timezone
    # must not be interpreted as Bishkek time or used to schedule a reminder.
    instant: datetime | None = None
    source_text: str | None = None
    conflict: bool = False


@dataclass(frozen=True, slots=True)
class EdersCourse:
    id: int
    name: str


@dataclass(frozen=True, slots=True)
class QuizAttempt:
    number: str | None
    submission: SubmissionStatus
    grading: GradingStatus
    grade: str | None = None


@dataclass(frozen=True, slots=True)
class EdersGrade:
    id: int
    course: EdersCourse
    name: str
    url: str
    grade: str | None = None
    range: str | None = None
    percentage: str | None = None
    feedback: str | None = None
    weight: str | None = None
    contribution: str | None = None
    visible_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EdersActivity:
    id: int
    course: EdersCourse
    kind: ActivityKind
    name: str
    url: str
    opens: ActivityDate = ActivityDate()
    closes: ActivityDate = ActivityDate()
    submission: SubmissionStatus = SubmissionStatus.UNKNOWN
    grading: GradingStatus = GradingStatus.UNKNOWN
    title_date_mismatch: bool = False
    first_seen: datetime | None = None
    section: str = ""
    attempts: tuple[QuizAttempt, ...] = ()
    quiz_result: str | None = None


@dataclass(frozen=True, slots=True)
class EdersSnapshot:
    activities: tuple[EdersActivity, ...]
    fetched_at: datetime
    grades: tuple[EdersGrade, ...] = ()
    # Old deadline-only snapshots must establish a separate grade baseline.
    grades_observed: bool = False
    catalog_observed: bool = False
    courses: tuple[EdersCourse, ...] = ()
    unavailable_grade_courses: tuple[int, ...] = ()
