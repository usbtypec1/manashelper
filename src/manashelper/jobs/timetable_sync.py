import logging

from aiogram import Bot
from dishka import AsyncContainer

from manashelper.jobs.common import get_user_locale, send_notification
from manashelper.localization.i18n import i18n
from manashelper.repositories.course_repository import CourseRepository
from manashelper.repositories.notification_settings_repository import NotificationSettingsRepository
from manashelper.repositories.user_repository import UserRepository
from manashelper.services.timetable_formatter import format_lesson_changes
from manashelper.services.timetable_sync import TimetableSyncService

logger = logging.getLogger(__name__)


async def sync_timetable_job(container: AsyncContainer, bot: Bot) -> None:
    try:
        async with container() as request_container:
            course_repository = await request_container.get(CourseRepository)
            course_ids = await course_repository.get_all_ids()
    except Exception:
        logger.exception("Failed to load course ids for timetable sync")
        return

    for course_id in course_ids:
        await _sync_course_timetable(container, bot, course_id)


async def _sync_course_timetable(container: AsyncContainer, bot: Bot, course_id: int) -> None:
    try:
        async with container() as request_container:
            timetable_sync_service = await request_container.get(TimetableSyncService)
            notification_settings_repository = await request_container.get(NotificationSettingsRepository)
            user_repository = await request_container.get(UserRepository)

            changes = await timetable_sync_service.synchronize_course_timetable(course_id)
            if not changes:
                return

            user_ids = await (
                notification_settings_repository.get_user_ids_tracking_course_with_schedule_changes_enabled(course_id)
            )
            if not user_ids:
                return

            for user_id in user_ids:
                locale = await get_user_locale(user_repository, user_id)
                with i18n.context(), i18n.use_locale(locale.value):
                    message = format_lesson_changes(changes)
                await send_notification(bot, user_id, message)
    except Exception:
        logger.exception("Failed to sync timetable for course %s", course_id)
