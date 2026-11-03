from datetime import UTC, datetime, timedelta

from aiogram.methods import SendMessage

from manashelper.modules.schedule.application.timetable_sync import LessonChange
from manashelper.modules.schedule.presentation.timetable_formatter import format_lesson_changes
from manashelper.modules.users.application.locale import LocaleService
from manashelper.modules.users.application.theme import ThemeService
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.outbox.service import OutboxService


class TelegramScheduleChangeSender:
    def __init__(self, outbox: OutboxService, locales: LocaleService, themes: ThemeService) -> None:
        self._outbox = outbox
        self._locales = locales
        self._themes = themes

    async def send(self, user_id: int, changes: list[LessonChange]) -> None:
        locale = await self._locales.get_locale(user_id)
        theme = await self._themes.get_theme(user_id)
        with i18n.context(), i18n.use_locale(locale.value), i18n.use_theme(theme):
            message = format_lesson_changes(changes)
        await self._outbox.enqueue(
            user_id,
            [SendMessage(chat_id=user_id, text=message)],
            expires_at=datetime.now(UTC) + timedelta(hours=6),
            category="schedule",
        )
