from aiogram import Bot

from manashelper.modules.schedule.application.timetable_sync import LessonChange
from manashelper.modules.schedule.presentation.timetable_formatter import format_lesson_changes
from manashelper.modules.users.application.locale import LocaleService
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.delivery import send_notification


class TelegramScheduleChangeSender:
    def __init__(self, bot: Bot, locales: LocaleService) -> None:
        self._bot = bot
        self._locales = locales

    async def send(self, user_id: int, changes: list[LessonChange]) -> None:
        locale = await self._locales.get_locale(user_id)
        with i18n.context(), i18n.use_locale(locale.value):
            message = format_lesson_changes(changes)
        await send_notification(self._bot, user_id, message)
