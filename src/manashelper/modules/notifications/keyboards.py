from datetime import UTC, datetime

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.modules.notifications.callbacks import BroadcastMuteCallback, NotificationSettingCallback
from manashelper.modules.notifications.settings import NotificationSetting, NotificationSettingsSummary
from manashelper.platform.telegram.callbacks import SettingsAction, SettingsCallback


def _mark(is_enabled: bool) -> str:
    return "✅" if is_enabled else "❌"


def build_notifications_keyboard(settings: NotificationSettingsSummary) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"{_mark(settings.schedule_changes_enabled)} {_('notifications.schedule_changes')}",
        callback_data=NotificationSettingCallback(setting=NotificationSetting.SCHEDULE_CHANGES),
    )
    builder.button(
        text=_("menu.food"),
        callback_data=SettingsCallback(action=SettingsAction.OPEN_FOOD_MENU_NOTIFICATIONS),
    )
    if settings.broadcast_muted_until is not None and settings.broadcast_muted_until > datetime.now(UTC):
        builder.button(text=_("notifications.resume_broadcasts"), callback_data=BroadcastMuteCallback(muted=False))
    builder.button(text=_("common.back"), callback_data=SettingsCallback(action=SettingsAction.BACK_TO_SETTINGS))
    builder.adjust(1)
    return builder.as_markup()
