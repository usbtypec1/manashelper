from aiogram import Bot

from manashelper.localization.locale import Locale
from manashelper.modules.obis.application.notification import ExamGradeChange, LessonSkipChange
from manashelper.modules.obis.presentation.formatter import format_exam_grade_change, format_lesson_skip_change
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.delivery import send_notification


class TelegramObisNotificationSender:
    def __init__(self, bot: Bot, user_id: int, locale: Locale) -> None:
        self._bot = bot
        self._user_id = user_id
        self._locale = locale

    async def exam_grade_changed(self, change: ExamGradeChange) -> None:
        with i18n.context(), i18n.use_locale(self._locale.value):
            text = format_exam_grade_change(change)
        await send_notification(self._bot, self._user_id, text)

    async def lesson_skips_changed(self, change: LessonSkipChange) -> None:
        with i18n.context(), i18n.use_locale(self._locale.value):
            text = format_lesson_skip_change(change)
        await send_notification(self._bot, self._user_id, text)
