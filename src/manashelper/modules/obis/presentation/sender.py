from aiogram.methods import SendMessage
from aiogram.utils.i18n import gettext as _

from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme
from manashelper.modules.obis.application.notification import ExamGradeChange, LessonSkipChange
from manashelper.modules.obis.presentation.formatter import format_exam_grade_change, format_lesson_skip_change
from manashelper.modules.obis.presentation.keyboards import build_login_keyboard
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.outbox.service import OutboxService


class TelegramObisNotificationSender:
    def __init__(self, outbox: OutboxService, user_id: int, locale: Locale, theme: Theme) -> None:
        self._outbox = outbox
        self._user_id = user_id
        self._locale = locale
        self._theme = theme

    async def exam_grade_changed(self, change: ExamGradeChange) -> None:
        with i18n.context(), i18n.use_locale(self._locale.value), i18n.use_theme(self._theme):
            text = format_exam_grade_change(change)
        await self._outbox.enqueue(
            self._user_id, [SendMessage(chat_id=self._user_id, text=text)], category="exam_grades"
        )

    async def lesson_skips_changed(self, change: LessonSkipChange) -> None:
        with i18n.context(), i18n.use_locale(self._locale.value), i18n.use_theme(self._theme):
            text = format_lesson_skip_change(change)
        await self._outbox.enqueue(
            self._user_id, [SendMessage(chat_id=self._user_id, text=text)], category="lesson_skips"
        )

    async def session_expired(self) -> None:
        with i18n.context(), i18n.use_locale(self._locale.value), i18n.use_theme(self._theme):
            method = SendMessage(
                chat_id=self._user_id, text=_("obis.session_expired"), reply_markup=build_login_keyboard()
            )
        await self._outbox.enqueue(self._user_id, [method], category="obis_session")
