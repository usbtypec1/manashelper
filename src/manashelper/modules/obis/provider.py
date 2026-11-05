from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.obis.application.credentials import ObisCredentialsQuery
from manashelper.modules.obis.application.ports import (
    AttendanceStore,
    CredentialsStore,
    CredentialsVerifier,
    ExamGradeStore,
    PasswordCipher,
    ResultsSource,
    SnapshotStore,
)
from manashelper.modules.obis.application.queries import ObisResultsQuery
from manashelper.modules.obis.application.use_cases.clear_obis_credentials import ClearObisCredentialsUseCase
from manashelper.modules.obis.application.use_cases.poll_obis_user import PollObisUserUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_attendance import RefreshObisAttendanceUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_grades import RefreshObisGradesUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_transcript import RefreshObisTranscriptUseCase
from manashelper.modules.obis.application.use_cases.save_obis_credentials import SaveObisCredentialsUseCase
from manashelper.modules.obis.infrastructure.client import ObisClient
from manashelper.modules.obis.infrastructure.crypto import CryptoService
from manashelper.modules.obis.infrastructure.repositories.credentials import ObisCredentialsRepository
from manashelper.modules.obis.infrastructure.repositories.snapshot import ObisSnapshotRepository
from manashelper.modules.obis.infrastructure.repositories.user_exam_grade import UserExamGradeRepository
from manashelper.modules.obis.infrastructure.repositories.user_lesson_attendance import UserLessonAttendanceRepository
from manashelper.modules.obis.infrastructure.results_source import ObisResultsSource


class ObisProvider(Provider):
    scope = Scope.REQUEST

    client = provide(ObisClient, scope=Scope.APP)
    crypto = provide(CryptoService, scope=Scope.APP)
    credentials_repository = provide(ObisCredentialsRepository)
    credentials = provide(ObisCredentialsQuery)
    grades = provide(UserExamGradeRepository)
    attendance = provide(UserLessonAttendanceRepository)
    results = provide(ObisResultsQuery)
    refresh_grades = provide(RefreshObisGradesUseCase)
    refresh_transcript = provide(RefreshObisTranscriptUseCase)
    refresh_attendance = provide(RefreshObisAttendanceUseCase)
    save_credentials = provide(SaveObisCredentialsUseCase)
    clear_credentials = provide(ClearObisCredentialsUseCase)
    polling = provide(PollObisUserUseCase)

    @provide(scope=Scope.APP)
    def verifier(self, client: ObisClient) -> CredentialsVerifier:
        return client

    @provide(scope=Scope.APP)
    def cipher(self, crypto: CryptoService) -> PasswordCipher:
        return crypto

    @provide
    def credential_store(self, repository: ObisCredentialsRepository) -> CredentialsStore:
        return repository

    @provide
    def grade_store(self, repository: UserExamGradeRepository) -> ExamGradeStore:
        return repository

    @provide
    def attendance_store(self, repository: UserLessonAttendanceRepository) -> AttendanceStore:
        return repository

    @provide(scope=Scope.APP)
    def source(self, client: ObisClient) -> ResultsSource:
        return ObisResultsSource(client)

    @provide
    def snapshots(self, session: AsyncSession) -> SnapshotStore:
        return ObisSnapshotRepository(session)
