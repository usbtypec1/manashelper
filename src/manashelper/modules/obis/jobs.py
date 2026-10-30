import logging

from aiogram import Bot
from dishka import AsyncContainer

from manashelper.modules.notifications.queries import NotificationRecipientsQuery
from manashelper.modules.obis.application.obis import ObisService
from manashelper.modules.obis.application.polling import PollObisUser
from manashelper.modules.obis.presentation.sender import TelegramObisNotificationSender
from manashelper.modules.users.application.locale import LocaleService
from manashelper.modules.users.application.theme import ThemeService

logger = logging.getLogger(__name__)


async def poll_obis_notifications_job(container: AsyncContainer, bot: Bot) -> None:
    try:
        async with container() as request_container:
            recipients = await request_container.get(NotificationRecipientsQuery)
            exam_grade_user_ids = set(await recipients.for_exam_grades())
            lesson_skip_user_ids = set(await recipients.for_lesson_skips())
            service = await request_container.get(ObisService)
            user_ids = await service.get_poll_user_ids()
    except Exception:
        logger.exception("Failed to load users for OBIS notification polling")
        return

    for user_id in user_ids:
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
            polling = await request_container.get(PollObisUser)
            locales = await request_container.get(LocaleService)
            locale = await locales.get_locale(user_id)
            themes = await request_container.get(ThemeService)
            theme = await themes.get_theme(user_id)
            sender = TelegramObisNotificationSender(bot, user_id, locale, theme)
            await polling.execute(user_id, check_exam_grades, check_lesson_skips, sender)
    except Exception:
        logger.exception("Failed to poll OBIS notifications for user %s", user_id)
