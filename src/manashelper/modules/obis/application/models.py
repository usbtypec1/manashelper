from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TranscriptCourse:
    code: str
    name: str
    grade: str


@dataclass(frozen=True, slots=True)
class TranscriptSemester:
    key: str
    credits: Decimal | None
    points: Decimal | None
    courses: tuple[TranscriptCourse, ...]


@dataclass(frozen=True, slots=True)
class Transcript:
    semesters: tuple[TranscriptSemester, ...]
    overall_gpa: Decimal


@dataclass(frozen=True, slots=True)
class ExamModel:
    name: str | None
    score: str | None


@dataclass(frozen=True, slots=True)
class LessonExamsModel:
    lesson_name: str | None
    lesson_code: str | None
    exams: list[ExamModel]


@dataclass(frozen=True, slots=True)
class AttendanceRecord:
    lesson_name: str
    lesson_code: str
    theory_skips_percentage: float | None
    practice_skips_percentage: float | None


@dataclass(frozen=True, slots=True)
class LessonAttendanceModel:
    lesson_name: str
    lesson_code: str
    theory_skips_percentage: float | None
    practice_skips_percentage: float | None
    theory_skippable: int | None
    practice_skippable: int | None


@dataclass(frozen=True, slots=True)
class Snapshot[T]:
    credential_marker: str
    lessons: list[T]
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class RefreshResult[T, C]:
    lessons: list[T]
    changes: list[C]


@dataclass(frozen=True, slots=True)
class StoredCredentials:
    student_number: str | None = field(repr=False)
    encrypted_password: str | None = field(repr=False)


@dataclass(frozen=True, slots=True)
class ObisLoginAttempt:
    """Server-side state of one OBIS login form: its cookies bind the captcha and CSRF token."""

    cookies: dict[str, str] = field(repr=False)
    csrf_token: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ObisLoginChallenge:
    attempt: ObisLoginAttempt
    captcha_image: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class PendingObisLogin:
    """Credentials waiting for a captcha answer; the password stays encrypted between messages."""

    student_number: str = field(repr=False)
    encrypted_password: str = field(repr=False)
    attempt: ObisLoginAttempt


@dataclass(frozen=True, slots=True)
class ObisCaptcha:
    pending: PendingObisLogin
    image: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class StoredObisSession:
    encrypted_cookies: str = field(repr=False)
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ExamGradeRecord:
    id: UUID | None
    lesson_code: str | None
    exam_name: str | None
    score: str | None


@dataclass(frozen=True, slots=True)
class AttendanceBaseline:
    id: UUID | None
    lesson_code: str
    theory_skips_percentage: float | None
    practice_skips_percentage: float | None
