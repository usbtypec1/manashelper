from types import SimpleNamespace

from manashelper.modules.obis.application.credentials import ObisCredentialsQuery
from manashelper.modules.obis.application.queries import ObisResultsQuery
from manashelper.modules.obis.application.use_cases.clear_obis_credentials import ClearObisCredentialsUseCase
from manashelper.modules.obis.application.use_cases.poll_obis_user import PollObisUserUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_attendance import RefreshObisAttendanceUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_grades import RefreshObisGradesUseCase
from manashelper.modules.obis.application.use_cases.save_obis_credentials import SaveObisCredentialsUseCase
from manashelper.modules.obis.infrastructure.repositories.credentials import ObisCredentialsRepository
from manashelper.modules.obis.infrastructure.repositories.snapshot import ObisSnapshotRepository
from manashelper.modules.obis.infrastructure.repositories.user_exam_grade import UserExamGradeRepository
from manashelper.modules.obis.infrastructure.repositories.user_lesson_attendance import UserLessonAttendanceRepository
from manashelper.modules.obis.infrastructure.results_source import ObisResultsSource


def build_obis(session, client, crypto):
    store = ObisCredentialsRepository(session)
    account = ObisCredentialsQuery(store, crypto)
    snapshots = ObisSnapshotRepository(session)
    source = ObisResultsSource(client)
    grades = RefreshObisGradesUseCase(account, store, source, snapshots, UserExamGradeRepository(session))
    attendance = RefreshObisAttendanceUseCase(
        account, store, source, snapshots, UserLessonAttendanceRepository(session)
    )
    return SimpleNamespace(
        client=client,
        account=account,
        results=ObisResultsQuery(account, snapshots),
        grades=grades,
        attendance=attendance,
        save=SaveObisCredentialsUseCase(account, store, client, crypto, snapshots),
        clear=ClearObisCredentialsUseCase(account, store, snapshots),
        poll=PollObisUserUseCase(grades, attendance),
    )
