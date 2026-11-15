from types import SimpleNamespace
from unittest.mock import AsyncMock

from manashelper.modules.gamification.application.use_cases.record_attendance import RecordAttendanceUseCase
from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository
from manashelper.modules.obis.application.access import ObisAccessService
from manashelper.modules.obis.application.credentials import ObisCredentialsQuery
from manashelper.modules.obis.application.models import ObisLoginAttempt, ObisLoginChallenge
from manashelper.modules.obis.application.ports import CaptchaRecognizer
from manashelper.modules.obis.application.queries import ObisResultsQuery
from manashelper.modules.obis.application.sessions import ObisSessions
from manashelper.modules.obis.application.use_cases.auto_login_obis import AutoLoginObisUseCase
from manashelper.modules.obis.application.use_cases.clear_obis_credentials import ClearObisCredentialsUseCase
from manashelper.modules.obis.application.use_cases.complete_obis_login import CompleteObisLoginUseCase
from manashelper.modules.obis.application.use_cases.poll_obis_user import PollObisUserUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_attendance import RefreshObisAttendanceUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_captcha import RefreshObisCaptchaUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_grades import RefreshObisGradesUseCase
from manashelper.modules.obis.application.use_cases.start_obis_login import StartObisLoginUseCase
from manashelper.modules.obis.infrastructure.captcha import LocalCaptchaRecognizer
from manashelper.modules.obis.infrastructure.repositories.auth_state import ObisAuthStateRepository
from manashelper.modules.obis.infrastructure.repositories.credentials import ObisCredentialsRepository
from manashelper.modules.obis.infrastructure.repositories.session import ObisSessionRepository
from manashelper.modules.obis.infrastructure.repositories.snapshot import ObisSnapshotRepository
from manashelper.modules.obis.infrastructure.repositories.user_exam_grade import UserExamGradeRepository
from manashelper.modules.obis.infrastructure.repositories.user_lesson_attendance import UserLessonAttendanceRepository
from manashelper.modules.obis.infrastructure.results_source import ObisResultsSource
from tests.modules.gamification.factories import build_awards

SESSION_COOKIES = {"PHPSESSID": "fake-session"}


def passthrough_access(cookies=SESSION_COOKIES):
    """Run the operation with isolated cookies while leaving access policy mocked."""
    access = AsyncMock(spec=ObisAccessService)

    async def with_session(user_id, operation):
        return await operation(dict(cookies))

    access.with_session.side_effect = with_session
    return access


def build_obis(session, client, crypto):
    """Compose OBIS with a real client or a mock whose manual login succeeds."""
    if isinstance(client, AsyncMock):
        client.start_login.return_value = ObisLoginChallenge(ObisLoginAttempt({"PHPSESSID": "form"}, "csrf"), b"png")
        client.complete_login.return_value = SESSION_COOKIES
    store = ObisCredentialsRepository(session)
    account = ObisCredentialsQuery(store, crypto)
    snapshots = ObisSnapshotRepository(session)
    sessions = ObisSessions(ObisSessionRepository(session), crypto)
    source = ObisResultsSource(client)
    auth_states = ObisAuthStateRepository(session)
    start = StartObisLoginUseCase(account, client, crypto, store)
    complete = CompleteObisLoginUseCase(account, store, client, crypto, snapshots, sessions, auth_states)
    refresh_captcha = RefreshObisCaptchaUseCase(client)
    recognizer = AsyncMock(spec=CaptchaRecognizer) if isinstance(client, AsyncMock) else LocalCaptchaRecognizer()
    auto_login = AutoLoginObisUseCase(start, complete, refresh_captcha, recognizer)
    access = ObisAccessService(store, sessions, auto_login, auth_states)
    grades = RefreshObisGradesUseCase(account, store, source, access, snapshots, UserExamGradeRepository(session))
    attendance = RefreshObisAttendanceUseCase(
        account,
        store,
        source,
        access,
        snapshots,
        UserLessonAttendanceRepository(session),
        RecordAttendanceUseCase(AchievementRepository(session), build_awards(session)),
    )

    async def login(user_id, student_number=None, password=None, code="code"):
        captcha = await start.execute(user_id, student_number, password)
        await complete.execute(user_id, captcha.pending, code)

    return SimpleNamespace(
        client=client,
        account=account,
        sessions=sessions,
        access=access,
        auth_states=auth_states,
        auto_login=auto_login,
        results=ObisResultsQuery(account, snapshots, sessions),
        grades=grades,
        attendance=attendance,
        start=start,
        refresh_captcha=refresh_captcha,
        complete=complete,
        login=login,
        clear=ClearObisCredentialsUseCase(account, store, snapshots, sessions, auth_states),
        poll=PollObisUserUseCase(grades, attendance, AsyncMock(), access),
    )
