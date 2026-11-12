from types import SimpleNamespace
from unittest.mock import AsyncMock

from manashelper.modules.gamification.application.use_cases.record_attendance import RecordAttendanceUseCase
from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository
from manashelper.modules.obis.application.credentials import ObisCredentialsQuery
from manashelper.modules.obis.application.models import ObisLoginAttempt, ObisLoginChallenge
from manashelper.modules.obis.application.queries import ObisResultsQuery
from manashelper.modules.obis.application.sessions import ObisSessions
from manashelper.modules.obis.application.use_cases.clear_obis_credentials import ClearObisCredentialsUseCase
from manashelper.modules.obis.application.use_cases.complete_obis_login import CompleteObisLoginUseCase
from manashelper.modules.obis.application.use_cases.poll_obis_user import PollObisUserUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_attendance import RefreshObisAttendanceUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_captcha import RefreshObisCaptchaUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_grades import RefreshObisGradesUseCase
from manashelper.modules.obis.application.use_cases.start_obis_login import StartObisLoginUseCase
from manashelper.modules.obis.infrastructure.repositories.credentials import ObisCredentialsRepository
from manashelper.modules.obis.infrastructure.repositories.session import ObisSessionRepository
from manashelper.modules.obis.infrastructure.repositories.snapshot import ObisSnapshotRepository
from manashelper.modules.obis.infrastructure.repositories.user_exam_grade import UserExamGradeRepository
from manashelper.modules.obis.infrastructure.repositories.user_lesson_attendance import UserLessonAttendanceRepository
from manashelper.modules.obis.infrastructure.results_source import ObisResultsSource
from tests.modules.gamification.factories import build_awards

SESSION_COOKIES = {"PHPSESSID": "fake-session"}


def build_obis(session, client, crypto):
    """Compose OBIS with a mocked ObisClient whose captcha login succeeds with SESSION_COOKIES."""
    client.start_login.return_value = ObisLoginChallenge(ObisLoginAttempt({"PHPSESSID": "form"}, "csrf"), b"png")
    client.complete_login.return_value = SESSION_COOKIES
    store = ObisCredentialsRepository(session)
    account = ObisCredentialsQuery(store, crypto)
    snapshots = ObisSnapshotRepository(session)
    sessions = ObisSessions(ObisSessionRepository(session), crypto)
    source = ObisResultsSource(client)
    grades = RefreshObisGradesUseCase(account, store, source, sessions, snapshots, UserExamGradeRepository(session))
    attendance = RefreshObisAttendanceUseCase(
        account,
        store,
        source,
        sessions,
        snapshots,
        UserLessonAttendanceRepository(session),
        RecordAttendanceUseCase(AchievementRepository(session), build_awards(session)),
    )
    start = StartObisLoginUseCase(account, client, crypto)
    complete = CompleteObisLoginUseCase(account, store, client, crypto, snapshots, sessions)

    async def login(user_id, student_number=None, password=None, code="code"):
        captcha = await start.execute(user_id, student_number, password)
        await complete.execute(user_id, captcha.pending, code)

    return SimpleNamespace(
        client=client,
        account=account,
        sessions=sessions,
        results=ObisResultsQuery(account, snapshots, sessions),
        grades=grades,
        attendance=attendance,
        start=start,
        refresh_captcha=RefreshObisCaptchaUseCase(client),
        complete=complete,
        login=login,
        clear=ClearObisCredentialsUseCase(account, store, snapshots, sessions),
        poll=PollObisUserUseCase(grades, attendance, AsyncMock(), sessions),
    )
