from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import NotificationSettingCallback, SettingsAction, SettingsCallback
from manashelper.services.notification_settings import NotificationSetting, NotificationSettingsSummary


def _mark(is_enabled: bool) -> str:
    return "✅" if is_enabled else "❌"


def build_settings_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("settings.notifications"), callback_data=SettingsCallback(action=SettingsAction.OPEN_NOTIFICATIONS)
    )
    builder.button(
        text=_("settings.my_lessons"), callback_data=SettingsCallback(action=SettingsAction.OPEN_COURSE_TRACKING)
    )
    builder.button(text=_("settings.obis_credentials"), callback_data=SettingsCallback(action=SettingsAction.OPEN_OBIS))
    builder.button(
        text=_("settings.phone_numbers"), callback_data=SettingsCallback(action=SettingsAction.OPEN_PHONE_NUMBERS)
    )
    builder.button(text=_("settings.language"), callback_data=SettingsCallback(action=SettingsAction.OPEN_LANGUAGE))
    builder.button(text=_("settings.feedback"), callback_data=SettingsCallback(action=SettingsAction.OPEN_FEEDBACK))
    builder.button(text=_("settings.donate"), callback_data=SettingsCallback(action=SettingsAction.OPEN_DONATIONS))
    builder.adjust(1)
    return builder.as_markup()


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
    builder.adjust(1)
    return builder.as_markup()
