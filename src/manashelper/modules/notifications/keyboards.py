from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.core.config import get_settings
from manashelper.modules.notifications.callbacks import NotificationSettingCallback
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
    builder.button(
        text=f"{_mark(settings.exam_grades_enabled)} {_('notifications.exam_grades')}",
        callback_data=NotificationSettingCallback(setting=NotificationSetting.EXAM_GRADES),
    )
    builder.button(
        text=f"{_mark(settings.lesson_skips_enabled)} {_('notifications.lesson_skips')}",
        callback_data=NotificationSettingCallback(setting=NotificationSetting.LESSON_SKIPS),
    )
    if get_settings().eders_enabled:
        builder.button(
            text=_("notifications.eders"),
            callback_data=SettingsCallback(action=SettingsAction.OPEN_EDERS_NOTIFICATIONS),
        )
    builder.button(text=_("common.back"), callback_data=SettingsCallback(action=SettingsAction.BACK_TO_SETTINGS))
    builder.adjust(1)
    return builder.as_markup()
