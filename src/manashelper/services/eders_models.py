from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class ActivityKind(StrEnum):
    ASSIGNMENT = "assign"
    QUIZ = "quiz"
    RESOURCE = "resource"
    LINK = "url"
    FOLDER = "folder"
    LABEL = "label"
    FORUM = "forum"
    FEEDBACK = "feedback"


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
    TODAY = "today"
    NOT_SUBMITTED = "not_submitted"
    MATERIALS = "materials"
    NEW_MATERIALS = "new_materials"


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
class EdersActivity:
    id: int
    course: EdersCourse
    kind: ActivityKind
    name: str
    url: str
    opens: ActivityDate = field(default_factory=ActivityDate)
    closes: ActivityDate = field(default_factory=ActivityDate)
    submission: SubmissionStatus = SubmissionStatus.UNKNOWN
    grading: GradingStatus = GradingStatus.UNKNOWN
    title_date_mismatch: bool = False
    first_seen: datetime | None = None
    section: str = ""
    description: str = ""


@dataclass(frozen=True, slots=True)
class EdersSnapshot:
    activities: tuple[EdersActivity, ...]
    fetched_at: datetime
    courses: tuple[EdersCourse, ...] = field(default_factory=tuple)
    schema_version: int = 2
