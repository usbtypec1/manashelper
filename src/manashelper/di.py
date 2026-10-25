from collections.abc import AsyncIterator

import httpx
from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from manashelper.config import Settings, get_settings
from manashelper.db.base import create_engine, create_session_pool
from manashelper.repositories.action_log_repository import ActionLogRepository
from manashelper.repositories.eders_repository import EdersRepository
from manashelper.repositories.notification_settings_repository import NotificationSettingsRepository
from manashelper.repositories.scheduled_message_deletion_repository import ScheduledMessageDeletionRepository
from manashelper.repositories.user_exam_grade_repository import UserExamGradeRepository
from manashelper.repositories.user_lesson_attendance_repository import UserLessonAttendanceRepository
from manashelper.repositories.user_phone_number_repository import UserPhoneNumberRepository
from manashelper.repositories.user_repository import UserRepository
from manashelper.scraping.eders_client import EdersClient
from manashelper.scraping.obis_client import ObisClient
from manashelper.services.action_log import ActionLogService
from manashelper.services.crypto import CryptoService
from manashelper.services.eders import EdersService
from manashelper.services.eders_tracking import EdersTrackingService
from manashelper.services.locale import LocaleService
from manashelper.services.message_deletion import MessageDeletionService
from manashelper.services.notification_settings import NotificationSettingsService
from manashelper.services.obis import ObisService
from manashelper.services.obis_notification import ObisNotificationService
from manashelper.services.study_week import StudyWeekService
from manashelper.services.user_contact import UserContactService


class AppProvider(Provider):
    scope = Scope.APP

    @provide
    def get_settings(self) -> Settings:
        return get_settings()

    @provide
    async def get_engine(self, settings: Settings) -> AsyncIterator[AsyncEngine]:
        engine = create_engine(settings)
        yield engine
        await engine.dispose()

    @provide
    def get_session_pool(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return create_session_pool(engine)

    @provide
    async def get_http_client(self) -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(timeout=15.0) as http_client:
            yield http_client

    crypto_service = provide(CryptoService)
    obis_client = provide(ObisClient)
    eders_client = provide(EdersClient)


class RequestProvider(Provider):
    scope = Scope.REQUEST

    @provide
    async def get_session(self, session_pool: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
        async with session_pool() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    user_repository = provide(UserRepository)
    eders_repository = provide(EdersRepository)
    notification_settings_repository = provide(NotificationSettingsRepository)
    user_exam_grade_repository = provide(UserExamGradeRepository)
    user_lesson_attendance_repository = provide(UserLessonAttendanceRepository)
    scheduled_message_deletion_repository = provide(ScheduledMessageDeletionRepository)
    action_log_repository = provide(ActionLogRepository)
    user_phone_number_repository = provide(UserPhoneNumberRepository)

    obis_service = provide(ObisService)
    eders_service = provide(EdersService)
    eders_tracking_service = provide(EdersTrackingService)
    notification_settings_service = provide(NotificationSettingsService)
    obis_notification_service = provide(ObisNotificationService)
    study_week_service = provide(StudyWeekService)
    locale_service = provide(LocaleService)
    message_deletion_service = provide(MessageDeletionService)
    action_log_service = provide(ActionLogService)
    user_contact_service = provide(UserContactService)
