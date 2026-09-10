import logging
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from dishka import AsyncContainer

from manashelper.bot.keyboards.food_menu_notifications import build_open_food_menu_notifications_keyboard
from manashelper.repositories.course_repository import CourseRepository
from manashelper.repositories.food_menu_notification_settings_repository import (
    FoodMenuNotificationSettingsRepository,
)
from manashelper.repositories.notification_settings_repository import NotificationSettingsRepository
from manashelper.scraping.obis_client import ObisLoginError
from manashelper.scraping.obis_parser import ObisParseError
from manashelper.services.daily_menu_service import BISHKEK_TZ, DailyMenuModel, DailyMenuNotFoundError, DailyMenuService
from manashelper.services.food_menu_formatter import build_photos, format_daily_menu
from manashelper.services.food_menu_sync_service import FoodMenuSyncService
from manashelper.services.obis_formatter import format_exam_grade_change, format_lesson_skip_change
from manashelper.services.obis_notification_service import ExamGradeChange, LessonSkipChange, ObisNotificationService
from manashelper.services.obis_service import UserHasNoCredentialsError
from manashelper.services.obis_service import UserNotFoundError as ObisUserNotFoundError
from manashelper.services.timetable_formatter import format_lesson_changes
from manashelper.services.timetable_sync_service import TimetableSyncService

logger = logging.getLogger(__name__)


async def sync_daily_menus_job(container: AsyncContainer) -> None:
    try:
        async with container() as request_container:
            service = await request_container.get(FoodMenuSyncService)
            await service.synchronize_daily_menus()
    except Exception:
        logger.exception("Failed to synchronize daily menus")


async def _send_daily_menu_broadcast(bot: Bot, daily_menu: DailyMenuModel, user_ids: list[int]) -> None:
    caption = format_daily_menu(daily_menu)
    media = build_photos(caption, daily_menu)
    keyboard = build_open_food_menu_notifications_keyboard()
    for user_id in user_ids:
        try:
            await bot.send_media_group(chat_id=user_id, media=media)
            await bot.send_message(chat_id=user_id, text="Приятного аппетита! 🍽", reply_markup=keyboard)
        except TelegramAPIError:
            logger.warning("Failed to send food menu broadcast to user %s", user_id, exc_info=True)


async def broadcast_lunch_menu_job(container: AsyncContainer, bot: Bot) -> None:
    try:
        async with container() as request_container:
            daily_menu_service = await request_container.get(DailyMenuService)
            food_menu_notification_settings_repository = await request_container.get(
                FoodMenuNotificationSettingsRepository
            )
            try:
                daily_menu = await daily_menu_service.get_daily_menu_by_skipping_days(0)
            except DailyMenuNotFoundError:
                logger.warning("No daily menu to broadcast for lunch")
                return
            weekday = datetime.now(BISHKEK_TZ).date().weekday()
            user_ids = await food_menu_notification_settings_repository.get_user_ids_with_lunch_enabled_for_weekday(
                weekday
            )
            await _send_daily_menu_broadcast(bot, daily_menu, user_ids)
    except Exception:
        logger.exception("Failed to broadcast lunch menu")


async def broadcast_dinner_menu_job(container: AsyncContainer, bot: Bot) -> None:
    try:
        async with container() as request_container:
            daily_menu_service = await request_container.get(DailyMenuService)
            food_menu_notification_settings_repository = await request_container.get(
                FoodMenuNotificationSettingsRepository
            )
            try:
                daily_menu = await daily_menu_service.get_daily_menu_by_skipping_days(0)
            except DailyMenuNotFoundError:
                logger.warning("No daily menu to broadcast for dinner")
                return
            weekday = datetime.now(BISHKEK_TZ).date().weekday()
            user_ids = await food_menu_notification_settings_repository.get_user_ids_with_dinner_enabled_for_weekday(
                weekday
            )
            await _send_daily_menu_broadcast(bot, daily_menu, user_ids)
    except Exception:
        logger.exception("Failed to broadcast dinner menu")


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

            if check_exam_grades:
                grade_changes = await _check_exam_grade_changes(obis_notification_service, user_id)
                for grade_change in grade_changes:
                    await _send_notification(bot, user_id, format_exam_grade_change(grade_change))

            if check_lesson_skips:
                skip_changes = await _check_lesson_skip_changes(obis_notification_service, user_id)
                for skip_change in skip_changes:
                    await _send_notification(bot, user_id, format_lesson_skip_change(skip_change))
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


async def _send_notification(bot: Bot, user_id: int, text: str) -> None:
    try:
        await bot.send_message(user_id, text)
    except TelegramAPIError:
        logger.warning("Failed to send notification to user %s", user_id, exc_info=True)


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

            changes = await timetable_sync_service.synchronize_course_timetable(course_id)
            if not changes:
                return

            user_ids = await (
                notification_settings_repository.get_user_ids_tracking_course_with_schedule_changes_enabled(course_id)
            )
            if not user_ids:
                return

            message = format_lesson_changes(changes)
            for user_id in user_ids:
                await _send_notification(bot, user_id, message)
    except Exception:
        logger.exception("Failed to sync timetable for course %s", course_id)
