from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import NotificationSettingCallback, SettingsAction, SettingsCallback
from manashelper.services.notification_settings_service import NotificationSetting, NotificationSettingsSummary


def _mark(is_enabled: bool) -> str:
    return "✅" if is_enabled else "❌"


def build_settings_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔔 Уведомления", callback_data=SettingsCallback(action=SettingsAction.OPEN_NOTIFICATIONS))
    builder.button(text="📚 Мои уроки", callback_data=SettingsCallback(action=SettingsAction.OPEN_COURSE_TRACKING))
    builder.adjust(1)
    return builder.as_markup()


def build_notifications_keyboard(
    settings: NotificationSettingsSummary,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"{_mark(settings.schedule_changes_enabled)} Изменения расписания",
        callback_data=NotificationSettingCallback(setting=NotificationSetting.SCHEDULE_CHANGES),
    )
    builder.button(
        text="🍉 Йемек",
        callback_data=SettingsCallback(action=SettingsAction.OPEN_FOOD_MENU_NOTIFICATIONS),
    )
    builder.button(
        text=f"{_mark(settings.exam_grades_enabled)} Оценки за экзамены",
        callback_data=NotificationSettingCallback(setting=NotificationSetting.EXAM_GRADES),
    )
    builder.button(
        text=f"{_mark(settings.lesson_skips_enabled)} Пропуски уроков",
        callback_data=NotificationSettingCallback(setting=NotificationSetting.LESSON_SKIPS),
    )
    builder.adjust(1)
    return builder.as_markup()


def build_food_menu_notifications_keyboard(
    settings: NotificationSettingsSummary,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"{_mark(settings.before_lunch_enabled)} Перед обедом",
        callback_data=NotificationSettingCallback(setting=NotificationSetting.BEFORE_LUNCH),
    )
    builder.button(
        text=f"{_mark(settings.before_dinner_enabled)} Перед ужином",
        callback_data=NotificationSettingCallback(setting=NotificationSetting.BEFORE_DINNER),
    )
    builder.button(
        text="◀️ Назад",
        callback_data=SettingsCallback(action=SettingsAction.BACK_TO_NOTIFICATIONS),
    )
    builder.adjust(1)
    return builder.as_markup()
