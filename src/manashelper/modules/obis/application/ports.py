from typing import Protocol

from manashelper.modules.obis.application.models import (
    AttendanceBaseline,
    AttendanceRecord,
    ExamGradeRecord,
    LessonAttendanceModel,
    LessonExamsModel,
    ObisLoginAttempt,
    ObisLoginChallenge,
    Snapshot,
    StoredCredentials,
    StoredObisSession,
    Transcript,
)
from manashelper.modules.obis.application.notification import ExamGradeChange, LessonSkipChange


class ObisNotificationSender(Protocol):
    async def exam_grade_changed(self, change: ExamGradeChange) -> None: ...

    async def lesson_skips_changed(self, change: LessonSkipChange) -> None: ...

    async def session_expired(self) -> None: ...


class ResultsSource(Protocol):
    """Fetch with saved session cookies; raises ObisSessionExpiredError when OBIS requires a new login."""

    async def fetch_transcript(self, cookies: dict[str, str]) -> Transcript: ...

    async def fetch_exam_grades(self, cookies: dict[str, str]) -> list[LessonExamsModel]: ...

    async def fetch_attendance(self, cookies: dict[str, str]) -> list[AttendanceRecord]: ...


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


class ObisAuthenticator(Protocol):
    async def start_login(self) -> ObisLoginChallenge: ...

    async def complete_login(
        self, attempt: ObisLoginAttempt, student_number: str, plain_password: str, captcha_code: str
    ) -> dict[str, str]:
        """Return authenticated session cookies; raise ObisCaptchaError or ObisLoginError."""
        ...


class SessionStore(Protocol):
    async def get(self, user_id: int) -> StoredObisSession | None: ...

    async def save(self, user_id: int, session: StoredObisSession) -> None: ...

    async def delete(self, user_id: int) -> StoredObisSession | None: ...


class PasswordCipher(Protocol):
    def encrypt(self, plain_text: str) -> str: ...

    def decrypt(self, encrypted_text: str) -> str: ...


class ExamGradeStore(Protocol):
    async def get_all_by_user_id(self, user_id: int) -> list[ExamGradeRecord]: ...

    async def save_all(self, user_id: int, records: list[ExamGradeRecord]) -> None: ...


class AttendanceStore(Protocol):
    async def get_all_by_user_id(self, user_id: int) -> list[AttendanceBaseline]: ...

    async def save_all(self, user_id: int, records: list[AttendanceBaseline]) -> None: ...
