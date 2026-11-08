from datetime import UTC, datetime

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.core.config import get_settings
from manashelper.modules.notifications.callbacks import BroadcastMuteCallback, NotificationSettingCallback
from manashelper.modules.notifications.settings import NotificationSetting, NotificationSettingsSummary
from manashelper.platform.telegram.callbacks import SettingsAction, SettingsCallback
from manashelper.platform.telegram.navigation import build_mini_app_button, build_navigation_keyboard


def _mark(is_enabled: bool) -> str:
    return "✅" if is_enabled else "❌"


def build_notifications_keyboard(settings: NotificationSettingsSummary) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    mini_app = build_mini_app_button()
    if mini_app is not None:
        builder.row(mini_app)
    for setting, label, enabled in (
        (NotificationSetting.SCHEDULE_CHANGES, _("notifications.schedule_changes"), settings.schedule_changes_enabled),
        (NotificationSetting.EXAM_GRADES, _("notifications.exam_grades"), settings.exam_grades_enabled),
        (NotificationSetting.LESSON_SKIPS, _("notifications.lesson_skips"), settings.lesson_skips_enabled),
    ):
        builder.button(text=f"{_mark(enabled)} {label}", callback_data=NotificationSettingCallback(setting=setting))
    builder.button(
        text=_("menu.food"),
        callback_data=SettingsCallback(action=SettingsAction.OPEN_FOOD_MENU_NOTIFICATIONS),
    )
    if get_settings().eders_enabled:
        builder.button(
            text=_("notifications.eders"),
            callback_data=SettingsCallback(action=SettingsAction.OPEN_EDERS_NOTIFICATIONS),
        )
    if settings.broadcast_muted_until is not None and settings.broadcast_muted_until > datetime.now(UTC):
        builder.button(text=_("notifications.resume_broadcasts"), callback_data=BroadcastMuteCallback(muted=False))
    else:
        builder.button(text=_("notifications.mute_broadcasts"), callback_data=BroadcastMuteCallback(muted=True))
    builder.button(text=_("common.back"), callback_data=SettingsCallback(action=SettingsAction.BACK_TO_SETTINGS))
    builder.adjust(1)
    builder.attach(build_navigation_keyboard())
    return builder.as_markup()
