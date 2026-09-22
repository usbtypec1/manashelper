import logging

from aiogram import Bot
from dishka import AsyncContainer

from manashelper.jobs.common import get_user_locale, send_notification
from manashelper.localization.i18n import i18n
from manashelper.repositories.notification_settings_repository import NotificationSettingsRepository
from manashelper.repositories.user_repository import UserRepository
from manashelper.scraping.obis_client import ObisLoginError
from manashelper.scraping.obis_parser import ObisParseError
from manashelper.services.obis import UserHasNoCredentialsError
from manashelper.services.obis import UserNotFoundError as ObisUserNotFoundError
from manashelper.services.obis_formatter import format_exam_grade_change, format_lesson_skip_change
from manashelper.services.obis_notification import ExamGradeChange, LessonSkipChange, ObisNotificationService

logger = logging.getLogger(__name__)


async def poll_obis_notifications_job(container: AsyncContainer, bot: Bot) -> None:
    try:
        async with container() as request_container:
            notification_settings_repository = await request_container.get(NotificationSettingsRepository)
            exam_grade_user_ids = set(await notification_settings_repository.get_user_ids_with_exam_grades_enabled())
            lesson_skip_user_ids = set(await notification_settings_repository.get_user_ids_with_lesson_skips_enabled())
    except Exception:
        logger.exception("Failed to load users for OBIS notification polling")
        return

    for user_id in exam_grade_user_ids | lesson_skip_user_ids:
        await _poll_user_obis_notifications(
            container, bot, user_id, user_id in exam_grade_user_ids, user_id in lesson_skip_user_ids
        )


async def _poll_user_obis_notifications(
    container: AsyncContainer,
    bot: Bot,
    user_id: int,
    check_exam_grades: bool,
    check_lesson_skips: bool,
) -> None:
    try:
        async with container() as request_container:
            obis_notification_service = await request_container.get(ObisNotificationService)
            user_repository = await request_container.get(UserRepository)
            locale = await get_user_locale(user_repository, user_id)

            if check_exam_grades:
                grade_changes = await _check_exam_grade_changes(obis_notification_service, user_id)
                for grade_change in grade_changes:
                    with i18n.context(), i18n.use_locale(locale.value):
                        text = format_exam_grade_change(grade_change)
                    await send_notification(bot, user_id, text)

            if check_lesson_skips:
                skip_changes = await _check_lesson_skip_changes(obis_notification_service, user_id)
                for skip_change in skip_changes:
                    with i18n.context(), i18n.use_locale(locale.value):
                        text = format_lesson_skip_change(skip_change)
                    await send_notification(bot, user_id, text)
    except Exception:
        logger.exception("Failed to poll OBIS notifications for user %s", user_id)


async def _check_exam_grade_changes(
    obis_notification_service: ObisNotificationService, user_id: int
) -> list[ExamGradeChange]:
    try:
        return await obis_notification_service.check_exam_grade_changes(user_id)
    except (ObisUserNotFoundError, UserHasNoCredentialsError, ObisLoginError, ObisParseError):
        return []


async def _check_lesson_skip_changes(
    obis_notification_service: ObisNotificationService, user_id: int
) -> list[LessonSkipChange]:
    try:
        return await obis_notification_service.check_lesson_skip_changes(user_id)
    except (ObisUserNotFoundError, UserHasNoCredentialsError, ObisLoginError, ObisParseError):
        return []
