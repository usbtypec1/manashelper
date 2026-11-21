from dataclasses import dataclass
from datetime import datetime

from aiogram.methods import SendMessage
from aiogram.utils.i18n import gettext as _

from manashelper.core.config import Settings
from manashelper.modules.gamification.application.queries import GamificationQuery
from manashelper.modules.gamification.presentation.catalog import achievement_strings
from manashelper.modules.gamification.presentation.keyboard import build_achievements_keyboard
from manashelper.modules.users.application.locale import LocaleQuery
from manashelper.modules.users.application.theme import ThemeQuery
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.html import escape_html
from manashelper.platform.telegram.outbox.service import OutboxService


def _achievement_source(user_id: int, key: str) -> str:
    return f"achievement:{user_id}:{key}"


@dataclass(frozen=True, slots=True)
class TelegramAchievementNotificationSender:
    outbox: OutboxService
    locales: LocaleQuery
    themes: ThemeQuery
    settings: Settings
    gamification: GamificationQuery

    async def earned(self, user_id: int, key: str, earned_at: datetime) -> None:
        display = await self.gamification.display_for(key)
        if display.hidden:
            return
        locale = await self.locales.get_locale(user_id)
        theme = await self.themes.get_theme(user_id)
        with i18n.context(), i18n.use_locale(locale.value), i18n.use_theme(theme):
            name, description = achievement_strings()[key]
            text = _("gamification.award_notification").format(
                name=escape_html(display.custom_name or name), description=escape_html(description)
            )
            keyboard = build_achievements_keyboard(self.settings.public_url) if self.settings.public_url else None
        source = _achievement_source(user_id, key)
        await self.outbox.enqueue(
            user_id,
            [SendMessage(chat_id=user_id, text=text, reply_markup=keyboard)],
            category="achievement",
            source_keys=[source],
            deduplication_key=f"{source}:{earned_at.isoformat()}",
        )

    async def cancel(self, user_id: int, key: str) -> None:
        await self.outbox.cancel_sources([_achievement_source(user_id, key)])
