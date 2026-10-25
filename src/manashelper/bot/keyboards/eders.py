from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import EdersPageCallback, EdersSettingCallback
from manashelper.platform.telegram.callbacks import SettingsAction, SettingsCallback
from manashelper.services.eders_models import DeadlineFilter
from manashelper.services.eders_tracking import EdersSetting, EdersSettings


def build_eders_keyboard(selected: DeadlineFilter, page: int, count: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for value, label in (
        (DeadlineFilter.ALL, _("eders.filter_all")),
        (DeadlineFilter.TODAY, _("eders.filter_today")),
        (DeadlineFilter.NEXT_SEVEN_DAYS, _("eders.filter_week")),
        (DeadlineFilter.AVAILABLE, _("eders.filter_available")),
        (DeadlineFilter.AWAITING_GRADE, _("eders.filter_awaiting")),
        (DeadlineFilter.UNKNOWN_DEADLINE, _("eders.filter_unknown")),
        (DeadlineFilter.NOT_SUBMITTED, _("eders.filter_not_submitted")),
        (DeadlineFilter.MATERIALS, _("eders.filter_materials")),
        (DeadlineFilter.NEW_MATERIALS, _("eders.filter_new_materials")),
    ):
        builder.button(
            text=f"✓ {label}" if value == selected else label,
            callback_data=EdersPageCallback(selected=value, page=0),
        )
    builder.adjust(1)
    navigation = InlineKeyboardBuilder()
    if page > 0:
        navigation.button(text="◀", callback_data=EdersPageCallback(selected=selected, page=page - 1))
    if page + 1 < count:
        navigation.button(text="▶", callback_data=EdersPageCallback(selected=selected, page=page + 1))
    builder.attach(navigation)
    return builder.as_markup()


def build_eders_settings_keyboard(settings: EdersSettings) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for setting, label in (
        (EdersSetting.DAY_BEFORE, _("eders.setting_day")),
        (EdersSetting.TWO_HOURS_BEFORE, _("eders.setting_two_hours")),
        (EdersSetting.OPENINGS, _("eders.setting_openings")),
        (EdersSetting.DEADLINE_CHANGES, _("eders.setting_changes")),
        (EdersSetting.HIDE_ARCHIVED, _("eders.setting_archived")),
        (EdersSetting.NEW_MATERIALS, _("eders.setting_materials")),
    ):
        marker = "✅" if getattr(settings, setting.value) else "⬜"
        builder.button(text=f"{marker} {label}", callback_data=EdersSettingCallback(setting=setting))
    builder.button(text=_("common.back"), callback_data=SettingsCallback(action=SettingsAction.BACK_TO_NOTIFICATIONS))
    builder.adjust(1)
    return builder.as_markup()
