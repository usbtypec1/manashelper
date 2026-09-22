from collections.abc import AsyncIterator

import httpx
from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from manashelper.config import Settings, get_settings
from manashelper.db.base import create_engine, create_session_pool
from manashelper.repositories.action_log_repository import ActionLogRepository
from manashelper.repositories.course_repository import CourseRepository
from manashelper.repositories.daily_menu_rating_repository import DailyMenuRatingRepository
from manashelper.repositories.daily_menu_repository import DailyMenuRepository
from manashelper.repositories.department_repository import DepartmentRepository
from manashelper.repositories.dish_repository import DishRepository
from manashelper.repositories.faculty_repository import FacultyRepository
from manashelper.repositories.food_menu_cleanup_settings_repository import FoodMenuCleanupSettingsRepository
from manashelper.repositories.food_menu_notification_settings_repository import (
    FoodMenuNotificationSettingsRepository,
)
from manashelper.repositories.lesson_history_repository import LessonHistoryRepository
from manashelper.repositories.lesson_repository import LessonRepository
from manashelper.repositories.notification_settings_repository import NotificationSettingsRepository
from manashelper.repositories.scheduled_message_deletion_repository import ScheduledMessageDeletionRepository
from manashelper.repositories.user_exam_grade_repository import UserExamGradeRepository
from manashelper.repositories.user_lesson_attendance_repository import UserLessonAttendanceRepository
from manashelper.repositories.user_repository import UserRepository
from manashelper.scraping.food_menu_client import FoodMenuClient
from manashelper.scraping.food_menu_parser import FoodMenuParser
from manashelper.scraping.obis_client import ObisClient
from manashelper.scraping.timetable_client import TimetableClient
from manashelper.services.action_log import ActionLogService
from manashelper.services.course import CourseService
from manashelper.services.crypto import CryptoService
from manashelper.services.daily_menu import DailyMenuService
from manashelper.services.department import DepartmentService
from manashelper.services.faculty import FacultyService
from manashelper.services.food_menu_cleanup_settings import FoodMenuCleanupSettingsService
from manashelper.services.food_menu_notification_settings import FoodMenuNotificationSettingsService
from manashelper.services.food_menu_sync import FoodMenuSyncService
from manashelper.services.lesson_search import LessonSearchService
from manashelper.services.locale import LocaleService
from manashelper.services.message_deletion import MessageDeletionService
from manashelper.services.notification_settings import NotificationSettingsService
from manashelper.services.obis import ObisService
from manashelper.services.obis_notification import ObisNotificationService
from manashelper.services.schedule import ScheduleService
from manashelper.services.timetable_sync import TimetableSyncService


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

    food_menu_client = provide(FoodMenuClient)
    food_menu_parser = provide(FoodMenuParser)
    crypto_service = provide(CryptoService)
    obis_client = provide(ObisClient)
    timetable_client = provide(TimetableClient)


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

    faculty_repository = provide(FacultyRepository)
    department_repository = provide(DepartmentRepository)
    course_repository = provide(CourseRepository)
    user_repository = provide(UserRepository)
    dish_repository = provide(DishRepository)
    daily_menu_repository = provide(DailyMenuRepository)
    daily_menu_rating_repository = provide(DailyMenuRatingRepository)
    notification_settings_repository = provide(NotificationSettingsRepository)
    food_menu_notification_settings_repository = provide(FoodMenuNotificationSettingsRepository)
    lesson_repository = provide(LessonRepository)
    lesson_history_repository = provide(LessonHistoryRepository)
    user_exam_grade_repository = provide(UserExamGradeRepository)
    user_lesson_attendance_repository = provide(UserLessonAttendanceRepository)
    scheduled_message_deletion_repository = provide(ScheduledMessageDeletionRepository)
    food_menu_cleanup_settings_repository = provide(FoodMenuCleanupSettingsRepository)
    action_log_repository = provide(ActionLogRepository)

    faculty_service = provide(FacultyService)
    department_service = provide(DepartmentService)
    course_service = provide(CourseService)
    daily_menu_service = provide(DailyMenuService)
    food_menu_sync_service = provide(FoodMenuSyncService)
    obis_service = provide(ObisService)
    notification_settings_service = provide(NotificationSettingsService)
    food_menu_notification_settings_service = provide(FoodMenuNotificationSettingsService)
    obis_notification_service = provide(ObisNotificationService)
    timetable_sync_service = provide(TimetableSyncService)
    schedule_service = provide(ScheduleService)
    lesson_search_service = provide(LessonSearchService)
    locale_service = provide(LocaleService)
    message_deletion_service = provide(MessageDeletionService)
    food_menu_cleanup_settings_service = provide(FoodMenuCleanupSettingsService)
    action_log_service = provide(ActionLogService)
