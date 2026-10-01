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
    opens: ActivityDate = ActivityDate()
    closes: ActivityDate = ActivityDate()
    submission: SubmissionStatus = SubmissionStatus.UNKNOWN
    grading: GradingStatus = GradingStatus.UNKNOWN
    title_date_mismatch: bool = False
    first_seen: datetime | None = None


@dataclass(frozen=True, slots=True)
class EdersSnapshot:
    activities: tuple[EdersActivity, ...]
    fetched_at: datetime
