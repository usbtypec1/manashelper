from typing import Protocol

from manashelper.modules.obis.application.models import (
    AttendanceBaseline,
    AttendanceRecord,
    ExamGradeRecord,
    LessonAttendanceModel,
    LessonExamsModel,
    Snapshot,
    StoredCredentials,
    Transcript,
)
from manashelper.modules.obis.application.notification import ExamGradeChange, LessonSkipChange


class ObisNotificationSender(Protocol):
    async def exam_grade_changed(self, change: ExamGradeChange) -> None: ...

    async def lesson_skips_changed(self, change: LessonSkipChange) -> None: ...


class ResultsSource(Protocol):
    async def fetch_transcript(self, student_number: str, password: str) -> Transcript: ...

    async def fetch_exam_grades(self, student_number: str, password: str) -> list[LessonExamsModel]: ...

    async def fetch_attendance(self, student_number: str, password: str) -> list[AttendanceRecord]: ...


class SnapshotStore(Protocol):
    """Read only the requested account's snapshot; None means absent or marker mismatch."""

    async def get_exam_grades(self, user_id: int, marker: str) -> list[LessonExamsModel] | None: ...

    async def get_attendance(self, user_id: int, marker: str) -> list[LessonAttendanceModel] | None: ...

    async def save_exam_grades(self, user_id: int, snapshot: Snapshot[LessonExamsModel]) -> None: ...

    async def save_attendance(self, user_id: int, snapshot: Snapshot[LessonAttendanceModel]) -> None: ...

    async def reset(self, user_id: int) -> None: ...

    async def get_poll_user_ids(self) -> list[int]: ...


class CredentialsStore(Protocol):
    async def get_by_user_id(self, user_id: int) -> StoredCredentials | None: ...

    async def save(self, user_id: int, credentials: StoredCredentials) -> None: ...

    async def lock(self, user_id: int) -> None: ...


class CredentialsVerifier(Protocol):
    async def verify_credentials(self, student_number: str, plain_password: str) -> None: ...


class PasswordCipher(Protocol):
    def encrypt(self, plain_text: str) -> str: ...

    def decrypt(self, encrypted_text: str) -> str: ...


class ExamGradeStore(Protocol):
    async def get_all_by_user_id(self, user_id: int) -> list[ExamGradeRecord]: ...

    async def save_all(self, user_id: int, records: list[ExamGradeRecord]) -> None: ...


class AttendanceStore(Protocol):
    async def get_all_by_user_id(self, user_id: int) -> list[AttendanceBaseline]: ...

    async def save_all(self, user_id: int, records: list[AttendanceBaseline]) -> None: ...
